"""手动打一次分, 把整个过程录下来 —— 页面结构变了就跑这个, 别再靠猜.

用法: python record_once.py
  1. 浏览器打开后自己登录 (如果需要)
  2. 在页面上手动点开某个同学的打分页, 把五项分数填好, **先不要提交**
  3. 回到终端按 Enter -> 录下"填好未提交"的状态
  4. 想连提交后的状态一起录, 就在页面上手动提交, 再按一次 Enter

产出: record_1_filled.html / record_2_submitted.html (完整页面) + 终端摘要
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
import time

URL = "http://172.31.126.2/StudentPage"

driver = webdriver.ChromiumEdge()
# driver = webdriver.Chrome()
driver.implicitly_wait(2)
driver.get(URL)
driver.maximize_window()


def snapshot(tag):
    print(f"\n===== 快照 {tag} =====")
    print("URL:", driver.current_url)
    print("标题:", driver.title)

    dialogs = driver.find_elements(By.CSS_SELECTOR, ".el-dialog, .el-drawer")
    print(f"对话框/抽屉: {len(dialogs)} 个 (>0 说明打分是弹窗, 不是独立路由)")

    print("-- 所有 input --")
    for n, el in enumerate(driver.find_elements(By.TAG_NAME, "input")):
        # 往上找两层, 把这个框旁边的文字带出来, 用来判断哪个框是德/智/体/美/劳
        try:
            label = driver.execute_script(
                "var p=arguments[0].closest('.el-form-item')||"
                "arguments[0].parentElement.parentElement;"
                "return p?p.innerText.replace(/\\s+/g,' ').slice(0,60):''",
                el,
            )
        except Exception:
            label = ""
        print(
            f"  [{n}] class={el.get_attribute('class')!r} "
            f"type={el.get_attribute('type')!r} "
            f"placeholder={el.get_attribute('placeholder')!r} "
            f"value={el.get_attribute('value')!r} "
            f"disabled={not el.is_enabled()} shown={el.is_displayed()} "
            f"附近文字={label!r}"
        )

    print("-- 所有 button --")
    for n, el in enumerate(driver.find_elements(By.TAG_NAME, "button")):
        print(
            f"  [{n}] text={el.text.strip()!r} class={el.get_attribute('class')!r} "
            f"shown={el.is_displayed()}"
        )

    path = f"record_{tag}.html"
    with open(path, "w", encoding="utf-8") as f:
        f.write(driver.page_source)
    print(f"完整页面已存到 {path}")


print(f"\n浏览器已打开 {URL}")
print("如果是空白, 手动刷新一下 (这系统进页面要刷一次才有内容)")
print("请手动: 登录 -> 点开一个同学的打分页 -> 填好五项分数 -> 【先不要提交】")
input("填好之后回到这里按 Enter 录制...")
snapshot("1_filled")

print("\n如果还想录提交后的状态: 现在去页面上手动点提交, 然后按 Enter")
print("(不想提交就直接 Ctrl+C 退出, 上面那份记录已经存好了)")
input()
time.sleep(1)
snapshot("2_submitted")

print("\n录完了. 把终端输出和 record_*.html 发给我, 我按真实结构改 auto_fill.py")
input("按 Enter 关闭浏览器...")
driver.quit()
