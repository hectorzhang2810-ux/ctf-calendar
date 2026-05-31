import logging
import sys

import click
from flask import Flask

from app.config import Config
from app.database import init_db, upsert_competition


def create_app(testing=False):
    app = Flask(__name__)
    app.config.from_object(Config)
    app.config['TESTING'] = testing

    if testing:
        app.config['DATABASE'] = ':memory:'

    logging.basicConfig(
        level=getattr(logging, Config.LOG_LEVEL),
        format='%(asctime)s %(levelname)s %(name)s %(message)s',
        stream=sys.stderr,
    )

    from app.database import get_db
    with app.app_context():
        init_db()

    from app import routes, admin, auth
    app.register_blueprint(routes.bp)
    app.register_blueprint(admin.bp)
    app.register_blueprint(auth.bp)

    @app.after_request
    def add_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '0'
        return response

    @app.cli.command('init-db')
    def cmd_init_db():
        init_db()
        click.echo('Database initialized.')

    @app.cli.command('fetch')
    @click.option('--source', default=None, help='Scraper source name')
    def cmd_fetch(source):
        found = 0
        from app.scrapers.hello_ctf import HelloCTFScraper
        from app.scrapers.nssctf import NSSCTFScraper
        from app.scrapers.ctfplus import CTFPlusScraper
        from app.scrapers.bugku import BugKuScraper
        from app.scrapers.ichunqiu import IChunQiuScraper
        from app.scrapers.provinces import ProvinceEduScraper

        scrapers = []
        enabled = Config.SCRAPER_ENABLED
        if (source is None or source == 'hello-ctf') and enabled.get('hello_ctf_cn', True):
            scrapers.append(HelloCTFScraper())
        # Province education department scrapers
        if source is None or source == 'province-edu':
            for province_key in Config.PROVINCE_EDUCATION_SITES:
                province_source = Config.PROVINCE_EDUCATION_SITES[province_key].get(
                    'source_name', f'{province_key}-edu'
                )
                if enabled.get(province_source, True):
                    scrapers.append(ProvinceEduScraper(province_key))
        if (source is None or source == 'nssctf') and enabled.get('nssctf', True):
            scrapers.append(NSSCTFScraper())
        if (source is None or source == 'ctfplus') and enabled.get('ctfplus', True):
            scrapers.append(CTFPlusScraper())
        if (source is None or source == 'bugku') and enabled.get('bugku', True):
            scrapers.append(BugKuScraper())
        if (source is None or source == 'ichunqiu') and enabled.get('ichunqiu', True):
            scrapers.append(IChunQiuScraper())

        for scraper in scrapers:
            click.echo(f'Fetching from {scraper.__class__.__name__}...')
            try:
                records = scraper.fetch()
                for rec in records:
                    upsert_competition(rec)
                click.echo(f'  OK: {len(records)} records')
                found += len(records)
            except Exception as e:
                click.echo(f'  FAILED: {e}', err=True)

        click.echo(f'Total: {found} records upserted.')

    @app.errorhandler(404)
    def not_found(e):
        return 'Not Found', 404

    @app.errorhandler(500)
    def server_error(e):
        return 'Internal Server Error', 500

    return app
