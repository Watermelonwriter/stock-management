import io
from datetime import datetime

import matplotlib.pyplot as plt
from flask import Flask, request, render_template_string, redirect, url_for, send_file
from openpyxl import Workbook

app = Flask(__name__)

inventory = {}

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
<a href="/export_xlsx">导出库存和消耗报表（Excel .xlsx 格式）</a>

<h2>系统操作</h2>
<form method="post" action="/clear_all" onsubmit="return confirm('确定要清空所有数据吗？此操作不可撤销！');">
    <button type="submit" style="background-color:red; color:white;">一键清空所有数据</button>
</form>
"""

@app.route("/")
def index():
    today = datetime.today().strftime("%Y-%m-%d")
    return render_template_string(HTML, inventory=inventory, today=today, enumerate=enumerate)

@app.route("/add_stock", methods=["POST"])
def add_stock():
    name = request.form["name"]
    date = request.form["date"]
    jin = int(request.form["jin"])
    liang = int(request.form["liang"])
    total_liang = jin * 10 + liang

    if name not in inventory:
        inventory[name] = {"stock": 0, "consumption": {}, "stock_records": []}
    inventory[name]["stock"] += total_liang
    inventory[name]["stock_records"].append({"date": date, "amount": total_liang})

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
    if inventory[name]["stock"] < total_liang:
        return "库存不足", 400

    inventory[name]["stock"] -= total_liang
    if date in inventory[name]["consumption"]:
        inventory[name]["consumption"][date] += total_liang
    else:
        inventory[name]["consumption"][date] = total_liang

    return redirect(url_for("index"))

@app.route("/delete_stock", methods=["POST"])
def delete_stock():
    name = request.form["name"]
    index = int(request.form["index"])
    if name in inventory and 0 <= index < len(inventory[name]["stock_records"]):
        rec = inventory[name]["stock_records"].pop(index)
        inventory[name]["stock"] -= rec["amount"]
        if inventory[name]["stock"] < 0:
            inventory[name]["stock"] = 0
    return redirect(url_for("index"))

@app.route("/delete_consume", methods=["POST"])
def delete_consume():
    name = request.form["name"]
    date = request.form["date"]
    if name in inventory and date in inventory[name]["consumption"]:
        amount = inventory[name]["consumption"].pop(date)
        inventory[name]["stock"] += amount
    return redirect(url_for("index"))

@app.route("/trend")
def trend():
    name = request.args.get("name")
    if not name or name not in inventory:
        return "菜品不存在", 400
    consumption = inventory[name]["consumption"]
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

@app.route("/export_xlsx")
def export_xlsx():
    wb = Workbook()

    # 进货记录表
    ws_stock = wb.active
    ws_stock.title = "进货记录"
    ws_stock.append(["菜品名称", "日期", "数量（斤）", "数量（两）"])
    for name, data in inventory.items():
        for rec in data.get("stock_records", []):
            jin = rec["amount"] // 10
            liang = rec["amount"] % 10
            ws_stock.append([name, rec["date"], jin, liang])

    # 消耗记录表
    ws_consume = wb.create_sheet(title="消耗记录")
    ws_consume.append(["菜品名称", "日期", "数量（斤）", "数量（两）"])
    for name, data in inventory.items():
        for date, amount in data.get("consumption", {}).items():
            jin = amount // 10
            liang = amount % 10
            ws_consume.append([name, date, jin, liang])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name="库存报表.xlsx"
    )

@app.route("/clear_all", methods=["POST"])
def clear_all():
    inventory.clear()
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug=True)
