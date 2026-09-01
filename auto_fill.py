page_num = 2  # 名单一共几页 (只用于收集学号)
# 打分列表, 依次为德智体美劳
# grades = ["20", "45", "10", "10", "10"]
grades = ["20", "50", "10", "10", "10"]
# grades = ["100", "100", "100", "100", "100"]

DRY_RUN = True  # True = 只填不提交. 提交不可撤销, 改成 False 前先跑一遍确认

ITEMS = ["德", "智", "体", "美", "劳"]  # grades 的顺序
BASE = "http://172.31.126.2"
STUDENT_LIST_URL = BASE + "/StudentPage"
ONLY_UNEVALUATED = True  # 只评"未评价"的, 避免重复提交

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.wait import WebDriverWait
import re
import time

driver = webdriver.ChromiumEdge()
# driver = webdriver.Chrome()
driver.implicitly_wait(2)

# 学校已经换成 CAS 统一身份认证了, 原来那个填学号当密码的表单已经没有路由.
# ENTRY_URL 可以留空: 那就直接开名单页, 你在弹出的窗口里手动完成统一身份认证.
# 如果你手上有从学校入口进来的带 token 直链, 也可以填在这里省掉登录那一步.
# 【别把带 token 的地址提交到仓库】—— 那是你账号的会话凭证.
ENTRY_URL = ""  # 例: BASE + "/evaluation?token=<你的token>&t=<...>&d=<...>"

driver.get(ENTRY_URL or STUDENT_LIST_URL)
driver.maximize_window()


def table_rows():
    """只读: 取列表页的表格行. 不要在这里 refresh —— 见 wait_for_rows."""
    return driver.find_elements(By.CSS_SELECTOR, ".el-table__row")


def score_inputs():
    """打分页上真正能填的输入框 (打分页挂着 4~5 个隐藏 el-dialog, 必须滤掉)."""
    return [
        el
        for el in driver.find_elements(By.CLASS_NAME, "el-input__inner")
        if el.is_displayed() and el.is_enabled()
    ]


def on_login_page():
    return any(m in driver.current_url for m in ("singlelogin", "/login", "sso.", "/cas"))


def wait_for_rows(refreshes=2):
    """列表页经常一片空白, 刷一次才渲染. 只在不是登录页时刷 ——
    早先把 refresh 放进 WebDriverWait 的谓词里, 结果登录页被 500ms 刷一次, 密码都输不完."""
    for attempt in range(refreshes + 1):
        for _ in range(10):
            rows = table_rows()
            if rows:
                return rows
            time.sleep(0.5)
        if on_login_page() or attempt == refreshes:
            break
        driver.refresh()
        time.sleep(3)
    return table_rows()


def col_index(title):
    headers = [
        th.text.strip()
        for th in driver.find_elements(By.CSS_SELECTOR, ".el-table__header th")
    ]
    idx = next((n for n, t in enumerate(headers) if title in t), None)
    if idx is None:
        print(f"表头里没有 {title!r}, 实际表头: {headers}")
        raise SystemExit(1)
    return idx


def goto_page(page):
    """翻页只用来收集名单. 打分不靠翻页 —— 见 detail_url."""
    if page == 1:
        return
    box = driver.find_elements(By.CSS_SELECTOR, ".el-pagination__editor input")
    if box:
        box[0].clear()
        box[0].send_keys(str(page), Keys.ENTER)
    else:
        for _ in range(1, page):
            driver.find_element(By.CLASS_NAME, "btn-next").click()
            time.sleep(1)
    time.sleep(3)


def read_page(page):
    """读当前页的 (学号, 姓名, 互评状态)."""
    wait_for_rows()
    goto_page(page)
    rows = wait_for_rows()
    i_sid, i_name, i_state = col_index("学号"), col_index("姓名"), col_index("班级互评")
    out = []
    for row in rows:
        tds = row.find_elements(By.TAG_NAME, "td")
        if len(tds) <= max(i_sid, i_name, i_state):
            continue
        out.append(
            (tds[i_sid].text.strip(), tds[i_name].text.strip(), tds[i_state].text.strip())
        )
    return out


def collect_roster():
    """把所有页的名单收齐.

    翻页有竞态: 跳到第 2 页后表格可能还是第 1 页的旧行, 这时候读出来的是第 1 页的人
    (上一轮 dry run 里第 2 页第 5 个就变成了第 1 页的王聪, 缴焕霖被整页漏掉).
    所以这里靠"和已收集的学号是否重叠"来判断读串了, 重叠就重读一次."""
    roster = []
    seen = set()
    for page in range(1, page_num + 1):
        for attempt in (1, 2, 3):
            got = read_page(page)
            ids = {sid for sid, _, _ in got}
            if page == 1 or not (ids & seen):
                break
            print(f"  第 {page} 页读到的学号和前面的重叠, 说明翻页没生效, 重读 (第 {attempt} 次)")
            driver.refresh()
            time.sleep(3)
        else:
            print(f"第 {page} 页反复读到重复内容, 停下 —— 不能拿错的名单去提交")
            raise SystemExit(1)

        new = [r for r in got if r[0] not in seen]
        seen.update(sid for sid, _, _ in new)
        roster.extend(new)
        print(f"  第 {page} 页: {len(new)} 人")
    return roster


def discover_plan_id():
    """打分页的地址是 /evaluation/list/<planId>/<学号>?breadNum=2.
    planId 每学期会变, 所以点一次第一个同学的打分图标, 从 URL 里读出来."""
    row = wait_for_rows()
    if not row:
        print("列表页没有行, 认不出 planId")
        raise SystemExit(1)
    row = row[0]
    cell = row.find_elements(By.TAG_NAME, "td")[col_index("打分")]
    icon = cell.find_elements(By.CSS_SELECTOR, ".action span, .action, span[title]")
    (icon[0] if icon else cell).click()
    for _ in range(20):
        m = re.search(r"/evaluation/list/(\d+)/", driver.current_url)
        if m:
            return m.group(1)
        time.sleep(0.5)
    print(f"点开打分页后没能从 URL 里认出 planId, 当前 URL: {driver.current_url}")
    raise SystemExit(1)


def item_of_inputs(blanks):
    """按文档顺序, 给每个输入框找它前面最近的"德/智/体/美/劳"字样.

    这五个框的 placeholder 全是空的, 光按位置填等于赌顺序 —— 德=20 和 智=50 一旦
    对调就是完全不同的分数, 而且提交不可撤销. 所以这里从 DOM 里把顺序读出来."""
    return driver.execute_script(
        """
        var targets = arguments[0], items = arguments[1];
        var out = new Array(targets.length).fill("");
        var last = "", w = document.createTreeWalker(
            document.body, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT, null);
        var n;
        while ((n = w.nextNode())) {
            if (n.nodeType === 3) {
                var t = n.textContent.trim();
                if (t && t.length <= 12) {
                    for (var i = 0; i < items.length; i++) {
                        if (t.indexOf(items[i]) !== -1) { last = items[i]; break; }
                    }
                }
            } else {
                var k = targets.indexOf(n);
                if (k !== -1) out[k] = last;
            }
        }
        return out;
        """,
        blanks,
        ITEMS,
    )


def fill_plan(blanks, verbose):
    """返回 [(项, 输入框, 分数)]. 能从 DOM 认出顺序就按顺序配, 认不出就按位置."""
    labels = item_of_inputs(blanks)
    if verbose:
        print(f"  [框的标签] {labels}")
    if sorted(labels) == sorted(ITEMS):  # 五项齐全且互不重复 = 顺序确定
        pos = {item: n for n, item in enumerate(labels)}
        if verbose:
            print(f"  [配对] 按 DOM 顺序配对成功: {labels}")
        return [(item, blanks[pos[item]], v) for item, v in zip(ITEMS, grades)]
    if verbose:
        print(f"  [配对] DOM 里认不出五项 ({labels}), 按位置填 —— 顺序假定为 {ITEMS}")
    return [(item, el, v) for item, el, v in zip(ITEMS, blanks, grades)]


def score_one(plan_id, sid, name, verbose):
    """直接按学号打开打分页. 不翻页、不 back(), 也就没有翻页竞态和重复提交."""
    driver.get(f"{BASE}/evaluation/list/{plan_id}/{sid}?breadNum=2")
    blanks = []
    for attempt in (1, 2):
        for _ in range(16):  # 8 秒
            blanks = score_inputs()
            if len(blanks) >= len(grades):
                break
            time.sleep(0.5)
        if len(blanks) >= len(grades):
            break
        if attempt == 1 and not on_login_page():  # 这系统进页面常常是空白, 刷一次
            driver.refresh()
            time.sleep(3)

    if len(blanks) < len(grades):
        print(f"  {sid} {name}: 只找到 {len(blanks)} 个输入框, 跳过")
        return False

    plan = fill_plan(blanks[: len(grades)], verbose)
    for _, blank, value in plan:
        blank.clear()
        blank.send_keys(value)
    filled = ", ".join(f"{item}={v}" for item, _, v in plan)

    button = driver.find_element(By.CLASS_NAME, "el-button--primary")
    if DRY_RUN:
        print(f"  DRY_RUN {sid} {name}: {filled}, 提交按钮={button.text.strip()!r}, 不提交")
        return True

    button.click()
    time.sleep(2)
    toast = [m.text.strip() for m in driver.find_elements(By.CSS_SELECTOR, ".el-message")]
    print(f"  已提交 {sid} {name}: {filled}" + (f" | 提示: {toast}" if toast else ""))
    return True


print("如果弹出登录页, 请在浏览器窗口里完成统一身份认证 (最多等 5 分钟)")
WebDriverWait(driver, 300).until(
    lambda d: not on_login_page()
    and (table_rows() or d.find_elements(By.CLASS_NAME, "submenu-title-noDropdown"))
)
if not wait_for_rows():
    print(f"登录后没看到名单, 直接打开 {STUDENT_LIST_URL}")
    driver.get(STUDENT_LIST_URL)
    if not wait_for_rows():
        print("还是没有名单. URL:", driver.current_url)
        print("正文:", repr(driver.find_element(By.TAG_NAME, "body").text[:400]))
        raise SystemExit(1)

print("收集名单...")
roster = collect_roster()
plan_id = discover_plan_id()
print(f"planId = {plan_id}, 名单共 {len(roster)} 人")

todo = [r for r in roster if not ONLY_UNEVALUATED or "未评价" in r[2]]
skipped = [r for r in roster if r not in todo]
for sid, name, state in skipped:
    print(f"  跳过 {sid} {name} (状态: {state})")

print(f"\n要打分的 {len(todo)} 人, 每人 {dict(zip(ITEMS, grades))}")
print("开始" + (" [DRY_RUN: 只填不提交]" if DRY_RUN else " [真提交, 不可撤销]"))
done = 0
for n, (sid, name, _) in enumerate(todo):
    if score_one(plan_id, sid, name, verbose=(n == 0)):
        done += 1

print(f"\nfinish: {done}/{len(todo)} 人" + (" (DRY_RUN, 什么都没提交)" if DRY_RUN else ""))
driver.quit()
