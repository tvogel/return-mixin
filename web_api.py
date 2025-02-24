from flask import Flask, request, jsonify, render_template_string
from return_mixin import get_pid, set_pid, control_loop as return_mixin_control_loop
from bwk_onoff import get_parameters, set_parameters, control_loop as bwk_onoff_control_loop
import threading
import time

app = Flask(__name__)

# Shared variables for diagnostics
return_mixin_diagnostics = []
bwk_onoff_diagnostics = []
return_mixin_lock = threading.Lock()
bwk_onoff_lock = threading.Lock()

@app.route('/', methods=['GET'])
def home():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Home</title>
        <style>
            body {
                font-family: Arial, sans-serif;
            }
        </style>
    </head>
    <body>
        <h1>Welcome to PyADS Control</h1>
        <a href="/return_mixin">Return Mix-in</a>
        <br>
        <a href="/bwk_onoff">BWK On/Off</a>
    </body>
    </html>
    '''

@app.route('/return_mixin', methods=['GET'])
def index():
    return render_template_string('''
    <!DOCTYPE html>
    <html>
    <head>
        <title>PyADS Control</title>
        <style>
            body {
                font-family: Arial, sans-serif;
            }
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
                const response = await fetch('/api/return-mixin/diagnostics');
                const data = await response.json();
                const table = document.getElementById('diagnostics');
                table.innerHTML = '<tr><th>dt</th><th>actual_value</th><th>error</th><th>I_error</th><th>D_error</th><th class="thick-border">P</th><th>I</th><th>D</th><th>control_output</th><th>new_control_value</th></tr>';
                data.forEach(row => {
                    const tr = document.createElement('tr');
                    const keys = ['dt', 'actual_value', 'error', 'I_error', 'D_error', 'P', 'I', 'D', 'control_output', 'new_control_value'];
                    keys.forEach((key) => {
                        const td = document.createElement('td');
                        td.innerText = row[key]?.toFixed(2) ?? '-';
                        if (key === 'P') {
                            td.classList.add('thick-border');
                        }
                        tr.appendChild(td);
                    });
                    table.appendChild(tr);
                });
            }

            async function fetchPID() {
                const response = await fetch('/api/return-mixin/pid');
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
                await fetch('/api/return-mixin/pid', {
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
        <a href="/">Home</a>
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

@app.route('/bwk_onoff', methods=['GET'])
def bwk_onoff_index():
    return render_template_string('''
    <!DOCTYPE html>
    <html>
    <head>
        <title>BWK On/Off Control</title>
        <style>
            body {
                font-family: Arial, sans-serif;
            }
            table {
                width: 60em;
                border-collapse: collapse;
            }
            th, td {
                border: 1px solid black;
                padding: 4px;
                text-align: left;
            }
            th {
                background-color: #CECECE;
            }
            tr:nth-child(even) {
                background-color: #E8E8E8;
            }
        </style>
        <script>
            function halfLifeToDecayFactor(halfLifeMinutes) {
                if (halfLifeMinutes <= 0) {
                    return 0;
                }
                return Math.pow(2, -1 / halfLifeMinutes / 60);
            }

            function decayFactorToHalfLife(decayFactor) {
                return - Math.log(2) / Math.log(decayFactor) / 60;
            }

            async function fetchDiagnostics() {
                const response = await fetch('/api/bwk-onoff/diagnostics');
                const data = await response.json();
                const table = document.getElementById('diagnostics');
                table.innerHTML = '<tr><th>Timestamp</th><th>Data</th></tr>';
                data.forEach(row => {
                    const tr = document.createElement('tr');
                    const tdTimestamp = document.createElement('td');
                    tdTimestamp.innerText = row.timestamp;
                    const tdData = document.createElement('td');
                    tdData.innerText = JSON.stringify(row.data);
                    tr.appendChild(tdTimestamp);
                    tr.appendChild(tdData);
                    table.appendChild(tr);
                });
            }

            async function fetchBWKParameters() {
                const response = await fetch('/api/bwk-onoff/parameters');
                const data = await response.json();
                document.getElementById('half_life_minutes').value = decayFactorToHalfLife(data.decay_factor).toFixed(2);
                document.getElementById('threshold').value = data.threshold;
                document.getElementById('auto_duration_minutes').value = data.auto_duration_minutes;
            }

            async function updateBWKParameters() {
                const half_life_minutes = Number(document.getElementById('half_life_minutes').value);
                const decay_factor = halfLifeToDecayFactor(half_life_minutes);
                const threshold = Number(document.getElementById('threshold').value);
                const auto_duration_minutes = Number(document.getElementById('auto_duration_minutes').value);
                await fetch('/api/bwk-onoff/parameters', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ decay_factor, threshold, auto_duration_minutes })
                });
                fetchBWKParameters();
            }

            setInterval(fetchDiagnostics, 5000);
            window.onload = function() {
                fetchDiagnostics();
                fetchBWKParameters();
            }
        </script>
    </head>
    <body>
        <h1>BWK On/Off Control</h1>
        <a href="/">Home</a>
        <h2>Diagnostics</h2>
        <table id="diagnostics"></table>
        <h2>Parameters</h2>
        <label for="half_life_minutes">Half-Life for exponential mean average (minutes):</label>
        <input type="number" id="half_life_minutes" step="0.01"><br>
        <label for="threshold">Threshold:</label>
        <input type="number" id="threshold" step="0.1"><br>
        <label for="auto_duration_minutes">Auto Duration (minutes):</label>
        <input type="number" id="auto_duration_minutes" step="0.1"><br>
        <button onclick="updateBWKParameters()">Update Parameters</button>
    </body>
    </html>
    ''')

@app.route('/api/return-mixin/diagnostics', methods=['GET'])
def get_return_mixin_diagnostics():
    with return_mixin_lock:
        return jsonify(return_mixin_diagnostics)

@app.route('/api/bwk-onoff/diagnostics', methods=['GET'])
def get_bwk_onoff_diagnostics():
    with bwk_onoff_lock:
        return jsonify(bwk_onoff_diagnostics)

@app.route('/api/return-mixin/pid', methods=['GET', 'POST'])
def pid_parameters():
    global Kp, Ki, Kd
    if request.method == 'POST':
        set_pid(request.json)
    return jsonify(get_pid())

@app.route('/api/bwk-onoff/parameters', methods=['GET', 'POST'])
def bwk_onoff_parameters():
    if request.method == 'POST':
        set_parameters(request.json)
    return jsonify(get_parameters())

def return_mixin_control_loop_with_diagnostics():
    global return_mixin_diagnostics
    while True:
        with return_mixin_lock:
            return_mixin_diagnostics.append(return_mixin_control_loop())
            if len(return_mixin_diagnostics) > 100:
                return_mixin_diagnostics.pop(0)
        time.sleep(5)

def bwk_onoff_control_loop_with_diagnostics():
    global bwk_onoff_diagnostics
    while True:
        with bwk_onoff_lock:
            diagnostics = bwk_onoff_control_loop()
            timestamp = diagnostics.pop('timestamp')
            bwk_onoff_diagnostics.append({'timestamp': timestamp, 'data': diagnostics})
            if len(bwk_onoff_diagnostics) > 100:
                bwk_onoff_diagnostics.pop(0)
        time.sleep(30)

def start_control_loops():
    return_mixin_thread = threading.Thread(target=return_mixin_control_loop_with_diagnostics)
    return_mixin_thread.daemon = True
    return_mixin_thread.start()

    bwk_onoff_thread = threading.Thread(target=bwk_onoff_control_loop_with_diagnostics)
    bwk_onoff_thread.daemon = True
    bwk_onoff_thread.start()

if __name__ == '__main__':
    start_control_loops()
    app.run(host='localhost', port=5000)

