from flask import Flask, request, jsonify, render_template_string
from return_mixin import get_pid, set_pid, control_loop
import threading
import time

app = Flask(__name__)

# Shared variables for diagnostics and PID parameters
diagnostics = []
lock = threading.Lock()

@app.route('/', methods=['GET'])
def index():
    return render_template_string('''
    <!DOCTYPE html>
    <html>
    <head>
        <title>PyADS Control</title>
        <style>
            table {
                width: 60em;
                border-collapse: collapse;
            }
            th, td {
                border: 1px solid black;
                padding: 4px;
                text-align: center;
            }
            th {
                background-color: #CECECE;
            }
            tr:nth-child(even) {
                background-color: #E8E8E8;
            }
            .thick-border {
                border-left: 3px solid black;
            }
        </style>
        <script>
            async function fetchDiagnostics() {
                const response = await fetch('/diagnostics');
                const data = await response.json();
                const table = document.getElementById('diagnostics');
                table.innerHTML = '<tr><th>dt</th><th>actual_value</th><th>error</th><th>I_error</th><th>D_error</th><th class="thick-border">P</th><th>I</th><th>D</th><th>control_output</th><th>new_control_value</th></tr>';
                data.forEach(row => {
                    const tr = document.createElement('tr');
                    const keys = ['dt', 'actual_value', 'error', 'I_error', 'D_error', 'P', 'I', 'D', 'control_output', 'new_control_value'];
                    keys.forEach((key) => {
                        const td = document.createElement('td');
                        td.innerText = row[key] !== null ? row[key].toFixed(2) : '-';
                        if (key === 'P') {
                            td.classList.add('thick-border');
                        }
                        tr.appendChild(td);
                    });
                    table.appendChild(tr);
                });
            }

            async function fetchPID() {
                const response = await fetch('/pid');
                const data = await response.json();
                document.getElementById('Kp').value = data.Kp;
                document.getElementById('Ki').value = data.Ki;
                document.getElementById('Kd').value = data.Kd;
                document.getElementById('set_point').value = data.set_point;
            }

            async function updatePID() {
                const Kp = Number(document.getElementById('Kp').value);
                const Ki = Number(document.getElementById('Ki').value);
                const Kd = Number(document.getElementById('Kd').value);
                const set_point = Number(document.getElementById('set_point').value);
                await fetch('/pid', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ Kp, Ki, Kd, set_point })
                });
                fetchPID();
            }

            setInterval(fetchDiagnostics, 5000);
            window.onload = function() {
                fetchDiagnostics();
                fetchPID();
            }
        </script>
    </head>
    <body>
        <h1>PyADS Control</h1>
        <h2>Diagnostics</h2>
        <table id="diagnostics"></table>
        <h2>PID Parameters</h2>
        <label for="Kp">Kp:</label>
        <input type="number" id="Kp" step="0.01"><br>
        <label for="Ki">Ki:</label>
        <input type="number" id="Ki" step="0.01"><br>
        <label for="Kd">Kd:</label>
        <input type="number" id="Kd" step="0.01"><br>
        <label for="set_point">Set Point:</label>
        <input type="number" id="set_point" step="0.1"><br>
        <button onclick="updatePID()">Update PID</button>
    </body>
    </html>
    ''')

@app.route('/diagnostics', methods=['GET'])
def get_diagnostics():
    with lock:
        return jsonify(diagnostics)

@app.route('/pid', methods=['GET', 'POST'])
def pid_parameters():
    global Kp, Ki, Kd
    if request.method == 'POST':
        set_pid(request.json)
    return jsonify(get_pid())

def control_loop_with_diagnostics():
    global diagnostics
    while True:
        with lock:
            diagnostics.append(control_loop())
            if len(diagnostics) > 100:
                diagnostics.pop(0)
        time.sleep(5)

def start_control_loop():
    thread = threading.Thread(target=control_loop_with_diagnostics)
    thread.daemon = True
    thread.start()

if __name__ == '__main__':
    start_control_loop()
    app.run(host='localhost', port=5000)

