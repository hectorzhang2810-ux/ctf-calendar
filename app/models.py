"""
数据模型常量
"""

# 比赛状态枚举
STATUS_REGISTERING = 'registering'   # 报名中
STATUS_ONGOING = 'ongoing'           # 进行中
STATUS_UPCOMING = 'upcoming'         # 即将开始
STATUS_FINISHED = 'finished'         # 已结束

STATUS_LABELS = {
    STATUS_REGISTERING: '报名中',
    STATUS_ONGOING: '进行中',
    STATUS_UPCOMING: '即将开始',
    STATUS_FINISHED: '已结束',
}

# 比赛类型
TYPE_CTF = 'CTF'
TYPE_HUWANG = '护网'
TYPE_ATTACK_DEFENSE = '攻防演练'
TYPE_OTHER = '其他'

# 比赛形式
FORMAT_JEOPARDY = 'Jeopardy'
FORMAT_AWD = 'AWD'
FORMAT_MIXED = '混合'
FORMAT_UNKNOWN = '未知'

# 参与方式
MODE_ONLINE = '线上'
MODE_OFFLINE = '线下'
MODE_HYBRID = '线上线下结合'


def compute_status(reg_start, reg_end, comp_start, comp_end):
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)

    def parse(s):
        if not s:
            return None
        try:
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except (ValueError, TypeError):
            return None

    cs = parse(comp_start)
    ce = parse(comp_end)
    rs = parse(reg_start)
    re_ = parse(reg_end)

    if ce and now > ce:
        return STATUS_FINISHED

    if cs and ce and cs <= now <= ce:
        return STATUS_ONGOING

    if rs and re_ and rs <= now <= re_:
        return STATUS_REGISTERING

    if cs and now < cs:
        return STATUS_UPCOMING

    return STATUS_UPCOMING


def normalize_name(name):
    """归一化比赛名称，用于去重"""
    import re
    # 去除空格、标点
    name = re.sub(r'[\s,，、。.。\s]', '', name)
    # 去除年份标记
    name = re.sub(r'20\d{2}', '', name)
    # 去除括号内容中的"第X届"
    name = re.sub(r'第[一二三四五六七八九十\d]+届', '', name)
    return name.lower()
