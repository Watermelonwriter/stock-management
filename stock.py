import matplotlib.pyplot as plt
from flask import Flask, request, render_template_string, redirect, url_for, send_file
from datetime import datetime
import io
import csv
import json
import os

app = Flask(__name__)

DATA_FILE = "inventory.json"

# 读取持久化数据
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        inventory = json.load(f)
else:
    inventory = {}

# 因为JSON中存的字典数据，字典里面是普通字典，我们用时方便写一个包装来转换回程序里的格式
# 但是本程序里用的是字典，不是自定义类，所以直接用字典即可

def save_inventory():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(inventory, f, ensure_ascii=False, indent=2)


HTML = """
<!doctype html>
<title>库存管理</title>

<h1>添加进货</h1>
<form method=post action="/add_stock">
  菜品名称: <input type=text name=name required><br>
  日期: <input type=date name=date value="{{today}}" required><br>
  斤: <input type=number name=jin min=0 required><br>
  两: <input type=number name=liang min=0 max=9 required><br>
  <input type=submit value=提交>
</form>

<h1>记录消耗</h1>
<form method=post action="/consume">
  菜品名称: <input type=text name=name required><br>
  日期(YYYY-MM-DD): <input type=date name=date required><br>
  斤: <input type=number name=jin min=0 required><br>
  两: <input type=number name=liang min=0 max=9 required><br>
  <input type=submit value=提交>
</form>

<h2>当前库存</h2>
<ul>
{% for name, data in inventory.items() %}
  <li>{{name}}: {{data.stock // 10}} 斤 {{data.stock % 10}} 两</li>
{% endfor %}
</ul>

<h2>查看消耗趋势</h2>
<form method=get action="/trend">
  菜品名称: <input type=text name=name required>
  <input type=submit value=查看>
</form>

<h2>进货记录管理</h2>
<ul>
{% for name, data in inventory.items() %}
  <li><b>{{name}}</b>
    <ul>
    {% for i, rec in enumerate(data.stock_records) %}
      <li>{{rec.date}} - {{rec.amount // 10}} 斤 {{rec.amount % 10}} 两
          <form method="post" action="/delete_stock" style="display:inline" onsubmit="return confirm('确定删除这条进货记录吗？');">
            <input type="hidden" name="name" value="{{name}}">
            <input type="hidden" name="index" value="{{i}}">
            <button type="submit">删除</button>
          </form>
      </li>
    {% endfor %}
    </ul>
  </li>
{% endfor %}
</ul>

<h2>消耗记录管理</h2>
<ul>
{% for name, data in inventory.items() %}
  <li><b>{{name}}</b>
    <ul>
    {% for date, amount in data.consumption.items() %}
      <li>{{date}} - {{amount // 10}} 斤 {{amount % 10}} 两
          <form method="post" action="/delete_consume" style="display:inline" onsubmit="return confirm('确定删除这条消耗记录吗？');">
            <input type="hidden" name="name" value="{{name}}">
            <input type="hidden" name="date" value="{{date}}">
            <button type="submit">删除</button>
          </form>
      </li>
    {% endfor %}
    </ul>
  </li>
{% endfor %}
</ul>

<br>
<a href="/export">导出库存和消耗报表（CSV）</a>

<h2>系统操作</h2>
<form method="post" action="/clear_all" onsubmit="return confirm('确定要清空所有数据吗？此操作不可撤销！');">
    <button type="submit" style="background-color:red; color:white;">一键清空所有数据</button>
</form>
"""

@app.route("/")
def index():
    today = datetime.today().strftime("%Y-%m-%d")
    # 因为json序列化后数字键会被转成字符串，jin和liang都是整数，stock_records的amount也都是整数
    # 这里不需要转，直接用字典
    # 但jin和liang计算中要确认类型
    # 为了Jinja渲染方便，我们做下转换，把库存和消费的键值都变成int，stock_records的amount也转成int
    inv = {}
    for name, data in inventory.items():
        inv[name] = {
            "stock": int(data.get("stock", 0)),
            "consumption": {k: int(v) for k, v in data.get("consumption", {}).items()},
            "stock_records": [{"date": rec["date"], "amount": int(rec["amount"])} for rec in data.get("stock_records", [])]
        }
    return render_template_string(HTML, inventory=inv, today=today, enumerate=enumerate)

@app.route("/add_stock", methods=["POST"])
def add_stock():
    name = request.form["name"]
    date = request.form["date"]
    jin = int(request.form["jin"])
    liang = int(request.form["liang"])
    total_liang = jin * 10 + liang

    if name not in inventory:
        inventory[name] = {"stock": 0, "consumption": {}, "stock_records": []}
    inventory[name]["stock"] = inventory[name].get("stock", 0) + total_liang
    inventory[name]["stock_records"].append({"date": date, "amount": total_liang})

    save_inventory()
    return redirect(url_for("index"))

@app.route("/consume", methods=["POST"])
def consume():
    name = request.form["name"]
    date = request.form["date"]
    jin = int(request.form["jin"])
    liang = int(request.form["liang"])
    total_liang = jin * 10 + liang

    if name not in inventory:
        return "菜品不存在", 400
    if inventory[name].get("stock", 0) < total_liang:
        return "库存不足", 400

    inventory[name]["stock"] -= total_liang
    if date in inventory[name].get("consumption", {}):
        inventory[name]["consumption"][date] += total_liang
    else:
        inventory[name]["consumption"][date] = total_liang

    save_inventory()
    return redirect(url_for("index"))

@app.route("/delete_stock", methods=["POST"])
def delete_stock():
    name = request.form["name"]
    index = int(request.form["index"])
    if name in inventory and 0 <= index < len(inventory[name].get("stock_records", [])):
        rec = inventory[name]["stock_records"].pop(index)
        inventory[name]["stock"] -= rec["amount"]
        if inventory[name]["stock"] < 0:
            inventory[name]["stock"] = 0

        save_inventory()
    return redirect(url_for("index"))

@app.route("/delete_consume", methods=["POST"])
def delete_consume():
    name = request.form["name"]
    date = request.form["date"]
    if name in inventory and date in inventory[name].get("consumption", {}):
        amount = inventory[name]["consumption"].pop(date)
        inventory[name]["stock"] += amount

        save_inventory()
    return redirect(url_for("index"))

@app.route("/trend")
def trend():
    name = request.args.get("name")
    if not name or name not in inventory:
        return "菜品不存在", 400
    consumption = inventory[name].get("consumption", {})
    if not consumption:
        return f"{name} 没有消耗记录"
    dates = sorted(consumption.keys())
    values = [consumption[d] / 10 for d in dates]

    plt.figure(figsize=(10, 5))
    plt.plot(dates, values, marker='o')
    plt.title(f"{name} 消耗趋势 (斤)")
    plt.xlabel("日期")
    plt.ylabel("消耗量 (斤)")
    plt.grid(True)
    plt.xticks(rotation=45)
    plt.tight_layout()

    import base64
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    img_base64 = base64.b64encode(buf.getvalue()).decode()
    plt.close()

    return f'''
    <h1>{name} 消耗趋势图</h1>
    <img src="data:image/png;base64,{img_base64}" />
    <br><a href="/">返回首页</a>
    '''

@app.route("/export")
def export():
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["进货记录"])
    writer.writerow(["菜品名称", "日期", "数量（斤）", "数量（两）"])
    for name, data in inventory.items():
        for rec in data.get("stock_records", []):
            jin = rec["amount"] // 10
            liang = rec["amount"] % 10
            writer.writerow([name, rec["date"], jin, liang])

    writer.writerow([])
    writer.writerow(["消耗记录"])
    writer.writerow(["菜品名称", "日期", "数量（斤）", "数量（两）"])
    for name, data in inventory.items():
        for date, amount in data.get("consumption", {}).items():
            jin = amount // 10
            liang = amount % 10
            writer.writerow([name, date, jin, liang])

    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode("utf-8")),
        mimetype="text/csv",
        as_attachment=True,
        download_name="库存报表.csv",
    )

@app.route("/clear_all", methods=["POST"])
def clear_all():
    inventory.clear()
    save_inventory()
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug=True)
