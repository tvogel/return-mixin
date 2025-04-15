from flask import Flask, request, jsonify, render_template_string
import return_mixin
import bwk_onoff
import pk_onoff
import bhkw_onoff
import feed_121517
import threading
import time
import asyncio

app = Flask(__name__)

# Shared variables for diagnostics
return_mixin_diagnostics = []
bwk_onoff_diagnostics = []
pk_onoff_diagnostics = []
bhkw_onoff_diagnostics = []
return_mixin_lock = threading.Lock()
bwk_onoff_lock = threading.Lock()
pk_onoff_lock = threading.Lock()
bhkw_onoff_lock = threading.Lock()

feed_121517_diagnostics = []
feed_121517_lock = threading.Lock()

common_styles = '''
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
    tr:nth-child(odd) {
        background-color: #E8E8E8;
    }
    .thick-border {
        border-left: 3px solid black;
    }
    .form-grid {
        display: grid;
        grid-template-columns: max-content auto;
        gap: 0.5em;
        align-items: center;
    }
    .form-grid label {
        text-align: right;
    }
    .form-grid button {
        grid-column: 2;
        justify-self: start;
    }
</style>
'''

@app.route('/', methods=['GET'])
def home():
    return render_template_string('''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Home</title>
        {{ common_styles|safe }}
    </head>
    <body>
        <h1>Welcome to PyADS Control</h1>
        <a href="/return_mixin">Return Mix-in</a>
        <br>
        <a href="/bwk_onoff">BWK On/Off</a>
        <br>
        <a href="/pk_onoff">PK On/Off</a>
        <br>
        <a href="/bhkw_onoff">BHKW On/Off</a>
        <br>
        <a href="/feed_121517">Feed 12/15/17</a>
    </body>
    </html>
    ''', common_styles=common_styles)

@app.route('/return_mixin', methods=['GET'])
def index():
    return render_template_string('''
    <!DOCTYPE html>
    <html>
    <head>
        <title>PyADS Control</title>
        {{ common_styles|safe }}
        <script>
            async function fetchDiagnostics() {
                const response = await fetch('/api/return-mixin/diagnostics');
                const data = await response.json();
                const table = document.getElementById('diagnostics');
                table.innerHTML = '<tr><th>dt</th><th>actual_value</th><th>error</th><th>I_error</th><th>D_error</th><th class="thick-border">P</th><th>I</th><th>D</th><th>control_output</th><th>new_control_value</th></tr>';
                data.reverse().forEach(row => {
                    const tr = document.createElement('tr');
                    const keys = ['dt', 'actual_value', 'error', 'I_error', 'D_error', 'P', 'I', 'D', 'control_output', 'new_control_value'];
                    const digits = { D_error: 4 };
                    keys.forEach((key) => {
                        const td = document.createElement('td');
                        td.innerText = row[key]?.toFixed(digits[key] ?? 2) ?? '-';
                        if (key === 'P') {
                            td.classList.add('thick-border');
                        }
                        tr.append(td);
                    });
                    table.append(tr);
                });
            }

            function halfLifeToDecayFactor(halfLifeMinutes) {
                if (halfLifeMinutes <= 0) {
                    return 0;
                }
                return Math.pow(2, -1 / halfLifeMinutes / 60);
            }

            function decayFactorToHalfLife(decayFactor) {
                return - Math.log(2) / Math.log(decayFactor) / 60;
            }

            async function fetchParameters() {
                const response = await fetch('/api/return-mixin/parameters');
                const data = await response.json();
                document.getElementById('Kp').value = data.Kp;
                document.getElementById('Ki').value = data.Ki;
                document.getElementById('Kd').value = data.Kd;
                document.getElementById('set_point').value = data.set_point;
                document.getElementById('off_range').value = data.off_range;
                document.getElementById('half_life_minutes').value = decayFactorToHalfLife(data.decay_factor).toFixed(2);
            }

            async function updateParameters() {
                const Kp = Number(document.getElementById('Kp').value);
                const Ki = Number(document.getElementById('Ki').value);
                const Kd = Number(document.getElementById('Kd').value);
                const set_point = Number(document.getElementById('set_point').value);
                const off_range = Number(document.getElementById('off_range').value);
                const half_life_minutes = Number(document.getElementById('half_life_minutes').value);
                const decay_factor = halfLifeToDecayFactor(half_life_minutes);
                await fetch('/api/return-mixin/parameters', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ Kp, Ki, Kd, set_point, off_range, decay_factor })
                });
                fetchParameters();
            }

            setInterval(fetchDiagnostics, 5000);
            window.onload = function() {
                fetchDiagnostics();
                fetchParameters();
            }
        </script>
    </head>
    <body>
        <h1>PyADS Control</h1>
        <a href="/">Home</a>
        <h2>PID Parameters</h2>
        <form class="form-grid" onsubmit="event.preventDefault(); updateParameters();">
            <label for="Kp">Kp:</label>
            <input type="number" id="Kp" step="0.00001">
            <label for="Ki">Ki:</label>
            <input type="number" id="Ki" step="0.00001">
            <label for="Kd">Kd:</label>
            <input type="number" id="Kd" step="0.00001">
            <label for="set_point">Set Point:</label>
            <input type="number" id="set_point" step="0.00001">
            <label for="off_range">Off-Range:</label>
            <input type="number" id="off_range" step="0.00001">
            <label for="half_life_minutes">Half-Life for exponential mean average (minutes):</label>
            <input type="number" id="half_life_minutes" step="0.00001">
            <button type="submit">Update PID</button>
        </form>
        <h2>Diagnostics</h2>
        <table id="diagnostics"></table>
    </body>
    </html>
    ''', common_styles=common_styles)

@app.route('/bwk_onoff', methods=['GET'])
def bwk_onoff_index():
    return render_template_string('''
    <!DOCTYPE html>
    <html>
    <head>
        <title>BWK On/Off Control</title>
        {{ common_styles|safe }}
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
                data.reverse().forEach(row => {
                    const tr = document.createElement('tr');
                    const tdTimestamp = document.createElement('td');
                    tdTimestamp.innerText = row.timestamp;
                    const tdData = document.createElement('td');
                    tdData.innerText = JSON.stringify(row.data);
                    tr.appendChild(tdTimestamp);
                    tr.appendChild(tdData);
                    table.append(tr);
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
        <h2>Parameters</h2>
        <form class="form-grid" onsubmit="event.preventDefault(); updateBWKParameters();">
            <label for="half_life_minutes">Half-Life for exponential mean average (minutes):</label>
            <input type="number" id="half_life_minutes" step="0.00001">
            <label for="threshold">Threshold:</label>
            <input type="number" id="threshold" step="0.00001">
            <label for="auto_duration_minutes">Auto Duration (minutes):</label>
            <input type="number" id="auto_duration_minutes" step="0.00001">
            <button type="submit">Update Parameters</button>
        </form>
        <h2>Diagnostics</h2>
        <table id="diagnostics"></table>
    </body>
    </html>
    ''', common_styles=common_styles)

@app.route('/pk_onoff', methods=['GET'])
def pk_onoff_index():
    return render_template_string('''
    <!DOCTYPE html>
    <html>
    <head>
        <title>PK On/Off Control</title>
        {{ common_styles|safe }}
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
                const response = await fetch('/api/pk-onoff/diagnostics');
                const data = await response.json();
                const table = document.getElementById('diagnostics');
                table.innerHTML = '<tr><th>Timestamp</th><th>Data</th></tr>';
                data.reverse().forEach(row => {
                    const tr = document.createElement('tr');
                    const tdTimestamp = document.createElement('td');
                    tdTimestamp.innerText = row.timestamp;
                    const tdData = document.createElement('td');
                    tdData.innerText = JSON.stringify(row.data);
                    tr.appendChild(tdTimestamp);
                    tr.appendChild(tdData);
                    table.append(tr);
                });
            }

            async function fetchPKParameters() {
                const response = await fetch('/api/pk-onoff/parameters');
                const data = await response.json();
                document.getElementById('half_life_minutes').value = decayFactorToHalfLife(data.decay_factor).toFixed(2);
                document.getElementById('on_threshold').value = data.on_threshold;
                document.getElementById('off_threshold').value = data.off_threshold;
            }

            async function updatePKParameters() {
                const half_life_minutes = Number(document.getElementById('half_life_minutes').value);
                const decay_factor = halfLifeToDecayFactor(half_life_minutes);
                const on_threshold = Number(document.getElementById('on_threshold').value);
                const off_threshold = Number(document.getElementById('off_threshold').value);
                await fetch('/api/pk-onoff/parameters', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ decay_factor, on_threshold, off_threshold })
                });
                fetchPKParameters();
            }

            setInterval(fetchDiagnostics, 5000);
            window.onload = function() {
                fetchDiagnostics();
                fetchPKParameters();
            }
        </script>
    </head>
    <body>
        <h1>PK On/Off Control</h1>
        <a href="/">Home</a>
        <h2>Parameters</h2>
        <form class="form-grid" onsubmit="event.preventDefault(); updatePKParameters();">
            <label for="half_life_minutes">Half-Life for exponential mean average (minutes):</label>
            <input type="number" id="half_life_minutes" step="0.00001">
            <label for="on_threshold">On Threshold:</label>
            <input type="number" id="on_threshold" step="0.00001">
            <label for="off_threshold">Off Threshold:</label>
            <input type="number" id="off_threshold" step="0.00001">
            <button type="submit">Update Parameters</button>
        </form>
        <h2>Diagnostics</h2>
        <table id="diagnostics"></table>
    </body>
    </html>
    ''', common_styles=common_styles)

@app.route('/bhkw_onoff', methods=['GET'])
def bhkw_onoff_index():
    return render_template_string('''
    <!DOCTYPE html>
    <html>
    <head>
        <title>BHKW On/Off Control</title>
        {{ common_styles|safe }}
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
                const response = await fetch('/api/bhkw-onoff/diagnostics');
                const data = await response.json();
                const table = document.getElementById('diagnostics');
                table.innerHTML = '<tr><th>Timestamp</th><th>Data</th></tr>';
                data.reverse().forEach(row => {
                    const tr = document.createElement('tr');
                    const tdTimestamp = document.createElement('td');
                    tdTimestamp.innerText = row.timestamp;
                    const tdData = document.createElement('td');
                    tdData.innerText = JSON.stringify(row.data);
                    tr.appendChild(tdTimestamp);
                    tr.appendChild(tdData);
                    table.append(tr);
                });
            }

            async function fetchParameters() {
                const response = await fetch('/api/bhkw-onoff/parameters');
                const data = await response.json();
                document.getElementById('on_threshold').value = data.on_threshold;
                document.getElementById('off_threshold').value = data.off_threshold;
                document.getElementById('half_life_minutes').value = decayFactorToHalfLife(data.decay_factor).toFixed(2);
            }

            async function updateParameters() {
                await fetch('/api/bhkw-onoff/parameters', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        decay_factor: halfLifeToDecayFactor(Number(document.getElementById('half_life_minutes').value)),
                        on_threshold: Number(document.getElementById('on_threshold').value),
                        off_threshold: Number(document.getElementById('off_threshold').value)
                    })
                });
                fetchParameters();
            }

            setInterval(fetchDiagnostics, 5000);
            window.onload = function() {
                fetchDiagnostics();
                fetchParameters();
            }
        </script>
    </head>
    <body>
        <h1>BHKW On/Off Control</h1>
        <a href="/">Home</a>
        <h2>Parameters</h2>
        <form class="form-grid" onsubmit="event.preventDefault(); updateParameters();">
            <label for="half_life_minutes">Half-Life for exponential mean average (minutes):</label>
            <input type="number" id="half_life_minutes" step="0.00001">
            <label for="on_threshold">On Threshold:</label>
            <input type="number" id="on_threshold" step="0.00001">
            <label for="off_threshold">Off Threshold:</label>
            <input type="number" id="off_threshold" step="0.00001">
            <button type="submit">Update Parameters</button>
        </form>
        <h2>Diagnostics</h2>
        <table id="diagnostics"></table>
    </body>
    </html>
    ''', common_styles=common_styles)

@app.route('/feed_121517', methods=['GET'])
def feed_121517_index():
    return render_template_string('''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Feed 12/15/17 Control</title>
        {{ common_styles|safe }}
        <script>
            async function fetchDiagnostics() {
                const response = await fetch('/api/feed-121517/diagnostics');
                const data = await response.json();
                const table = document.getElementById('diagnostics');
                table.innerHTML = `
                    <tr><th>Timestamp</th><th colspan="8" class="thick-border">Return Values</th><th colspan="8" class="thick-border">Circulation Values</th><th colspan="2" class="thick-border">Control</th></tr>
                    <tr>
                        <th></th><th class="thick-border">Actual</th><th>Error</th><th>I_error</th><th>D_error</th><th>P</th><th>I</th><th>D</th><th>Control</th>
                        <th class="thick-border">Actual</th><th>Error</th><th>I_error</th><th>D_error</th><th>P</th><th>I</th><th>D</th><th>Control</th>
                        <th class="thick-border">Output</th><th>New Value</th>
                    </tr>`;
                const keys = ['timestamp', 'return.actual', 'return.error', 'return.I_error', 'return.D_error', 'return.P', 'return.I', 'return.D', 'return.control',
                                'circulation.actual', 'circulation.error', 'circulation.I_error', 'circulation.D_error', 'circulation.P', 'circulation.I', 'circulation.D', 'circulation.control',
                                'control_output', 'new_control_value'];
                const digits = { 'return.D_error': 4, 'circulation.D_error': 4 };
                function formatValue(value, digits) {
                    return (typeof value === 'number' ? value.toFixed(digits) : value) ?? '-';
                }
                data.reverse().forEach(row => {
                    const tr = document.createElement('tr');
                    keys.forEach((key) => {
                        const td = document.createElement('td');
                        const value = key.split('.').reduce((o, k) => (o || {})[k], row);
                        td.innerText = formatValue(value, digits[key] ?? 2);
                        if (key === 'return.actual' || key === 'circulation.actual' || key === 'control_output') {
                            td.classList.add('thick-border');
                        }
                        tr.append(td);
                    });
                    table.append(tr);
                });
            }

            function halfLifeToDecayFactor(halfLifeMinutes) {
                if (halfLifeMinutes <= 0) {
                    return 0;
                }
                return Math.pow(2, -1 / halfLifeMinutes / 60);
            }

            function decayFactorToHalfLife(decayFactor) {
                return - Math.log(2) / Math.log(decayFactor) / 60;
            }

            async function fetchParameters() {
                const response = await fetch('/api/feed-121517/parameters');
                const data = await response.json();
                document.getElementById('return_set_point').value = data.return_set_point.toFixed(2);
                document.getElementById('circulation_set_point').value = data.circulation_set_point.toFixed(2);
                document.getElementById('return_Kp').value = data.return_pid.Kp.toFixed(4);
                document.getElementById('return_Ki').value = data.return_pid.Ki.toFixed(4);
                document.getElementById('return_Kd').value = data.return_pid.Kd.toFixed(4);
                document.getElementById('return_integration_half_life_minutes').value = decayFactorToHalfLife(data.return_pid.integration_decay_factor).toFixed(2);
                document.getElementById('circulation_Kp').value = data.circulation_pid.Kp.toFixed(4);
                document.getElementById('circulation_Ki').value = data.circulation_pid.Ki.toFixed(4);
                document.getElementById('circulation_Kd').value = data.circulation_pid.Kd.toFixed(4);
                document.getElementById('circulation_integration_half_life_minutes').value = decayFactorToHalfLife(data.circulation_pid.integration_decay_factor).toFixed(2);
            }

            async function updateParameters() {
                const return_set_point = Number(document.getElementById('return_set_point').value);
                const circulation_set_point = Number(document.getElementById('circulation_set_point').value);
                const return_Kp = Number(document.getElementById('return_Kp').value);
                const return_Ki = Number(document.getElementById('return_Ki').value);
                const return_Kd = Number(document.getElementById('return_Kd').value);
                const return_integration_half_life_minutes = Number(document.getElementById('return_integration_half_life_minutes').value);
                const circulation_Kp = Number(document.getElementById('circulation_Kp').value);
                const circulation_Ki = Number(document.getElementById('circulation_Ki').value);
                const circulation_Kd = Number(document.getElementById('circulation_Kd').value);
                const circulation_integration_half_life_minutes = Number(document.getElementById('circulation_integration_half_life_minutes').value);
                await fetch('/api/feed-121517/parameters', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        return_set_point,
                        circulation_set_point,
                        return_pid: { Kp: return_Kp, Ki: return_Ki, Kd: return_Kd, integration_decay_factor: halfLifeToDecayFactor(return_integration_half_life_minutes) },
                        circulation_pid: { Kp: circulation_Kp, Ki: circulation_Ki, Kd: circulation_Kd, integration_decay_factor: halfLifeToDecayFactor(circulation_integration_half_life_minutes) }
                    })
                });
                fetchParameters();
            }

            setInterval(fetchDiagnostics, 5000);
            window.onload = function() {
                fetchDiagnostics();
                fetchParameters();
            }
        </script>
    </head>
    <body>
        <h1>Feed 12/15/17 Control</h1>
        <a href="/">Home</a>
        <h2>PID Parameters</h2>
        <form class="form-grid" onsubmit="event.preventDefault(); updateParameters();">
            <label for="return_set_point">Return Set Point:</label>
            <input type="number" id="return_set_point" step="0.00001">
            <label for="circulation_set_point">Circulation Set Point:</label>
            <input type="number" id="circulation_set_point" step="0.00001">
            <label for="return_Kp">Return Kp:</label>
            <input type="number" id="return_Kp" step="0.00001">
            <label for="return_Ki">Return Ki:</label>
            <input type="number" id="return_Ki" step="0.00001">
            <label for="return_Kd">Return Kd:</label>
            <input type="number" id="return_Kd" step="0.00001">
            <label for="return_integration_half_life_minutes">Return Integration Half-Life (minutes):</label>
            <input type="number" id="return_integration_half_life_minutes" step="0.00001">
            <label for="circulation_Kp">Circulation Kp:</label>
            <input type="number" id="circulation_Kp" step="0.00001">
            <label for="circulation_Ki">Circulation Ki:</label>
            <input type="number" id="circulation_Ki" step="0.00001">
            <label for="circulation_Kd">Circulation Kd:</label>
            <input type="number" id="circulation_Kd" step="0.00001">
            <label for="circulation_integration_half_life_minutes">Circulation Integration Half-Life (minutes):</label>
            <input type="number" id="circulation_integration_half_life_minutes" step="0.00001">
            <button type="submit">Update PID</button>
        </form>
        <h2>Diagnostics</h2>
        <table id="diagnostics"></table>
    </body>
    </html>
    ''', common_styles=common_styles)

@app.route('/api/return-mixin/diagnostics', methods=['GET'])
def get_return_mixin_diagnostics():
    with return_mixin_lock:
        return jsonify(return_mixin_diagnostics)

@app.route('/api/bwk-onoff/diagnostics', methods=['GET'])
def get_bwk_onoff_diagnostics():
    with bwk_onoff_lock:
        return jsonify(bwk_onoff_diagnostics)

@app.route('/api/pk-onoff/diagnostics', methods=['GET'])
def get_pk_onoff_diagnostics():
    with pk_onoff_lock:
        return jsonify(pk_onoff_diagnostics)

@app.route('/api/bhkw-onoff/diagnostics', methods=['GET'])
def get_bhkw_onoff_diagnostics():
    with bhkw_onoff_lock:
        return jsonify(bhkw_onoff_diagnostics)

@app.route('/api/feed-121517/diagnostics', methods=['GET'])
def get_feed_121517_diagnostics():
    with feed_121517_lock:
        return jsonify(feed_121517_diagnostics)

@app.route('/api/return-mixin/parameters', methods=['GET', 'POST'])
def return_mixin_parameters():
    if request.method == 'POST':
        return_mixin.set_parameters(request.json)
    return jsonify(return_mixin.get_parameters())

@app.route('/api/bwk-onoff/parameters', methods=['GET', 'POST'])
def bwk_onoff_parameters():
    if request.method == 'POST':
        bwk_onoff.set_parameters(request.json)
    return jsonify(bwk_onoff.get_parameters())

@app.route('/api/pk-onoff/parameters', methods=['GET', 'POST'])
def pk_onoff_parameters():
    if request.method == 'POST':
        pk_onoff.set_parameters(request.json)
    return jsonify(pk_onoff.get_parameters())

@app.route('/api/bhkw-onoff/parameters', methods=['GET', 'POST'])
def bhkw_onoff_parameters():
    if request.method == 'POST':
        bhkw_onoff.set_parameters(request.json)
    return jsonify(bhkw_onoff.get_parameters())

@app.route('/api/feed-121517/parameters', methods=['GET', 'POST'])
def feed_121517_parameters():
    if request.method == 'POST':
        feed_121517.set_parameters(request.json)
    return jsonify(feed_121517.get_parameters())

async def feed_121517_combined_loop():
    await feed_121517.setup_mqtt()  # Start MQTT setup
    while True:
        diagnostics = await feed_121517.control_loop()
        with feed_121517_lock:
            feed_121517_diagnostics.append(diagnostics)
            if len(feed_121517_diagnostics) > 1000:
                feed_121517_diagnostics.pop(0)
        await asyncio.sleep(30)

def feed_121517_control_loop_with_diagnostics():
    asyncio.run(feed_121517_combined_loop())

def return_mixin_control_loop_with_diagnostics():
    global return_mixin_diagnostics
    while True:
        with return_mixin_lock:
            return_mixin_diagnostics.append(return_mixin.control_loop())
            if len(return_mixin_diagnostics) > 100:
                return_mixin_diagnostics.pop(0)
        time.sleep(5)

def bwk_onoff_control_loop_with_diagnostics():
    global bwk_onoff_diagnostics
    while True:
        with bwk_onoff_lock:
            diagnostics = bwk_onoff.control_loop()
            timestamp = diagnostics.pop('timestamp')
            bwk_onoff_diagnostics.append({'timestamp': timestamp, 'data': diagnostics})
            if len(bwk_onoff_diagnostics) > 100:
                bwk_onoff_diagnostics.pop(0)
        time.sleep(30)

def pk_onoff_control_loop_with_diagnostics():
    global pk_onoff_diagnostics
    while True:
        with pk_onoff_lock:
            diagnostics = pk_onoff.control_loop()
            timestamp = diagnostics.pop('timestamp')
            pk_onoff_diagnostics.append({'timestamp': timestamp, 'data': diagnostics})
            if len(pk_onoff_diagnostics) > 100:
                pk_onoff_diagnostics.pop(0)
        time.sleep(30)

def bhkw_onoff_control_loop_with_diagnostics():
    global bhkw_onoff_diagnostics
    while True:
        with bhkw_onoff_lock:
            diagnostics = bhkw_onoff.control_loop()
            timestamp = diagnostics.pop('timestamp')
            bhkw_onoff_diagnostics.append({'timestamp': timestamp, 'data': diagnostics})
            if len(bhkw_onoff_diagnostics) > 100:
                bhkw_onoff_diagnostics.pop(0)
        time.sleep(30)

def start_control_loops():
    return_mixin_thread = threading.Thread(target=return_mixin_control_loop_with_diagnostics)
    return_mixin_thread.daemon = True
    return_mixin_thread.start()

    bwk_onoff_thread = threading.Thread(target=bwk_onoff_control_loop_with_diagnostics)
    bwk_onoff_thread.daemon = True
    bwk_onoff_thread.start()

    pk_onoff_thread = threading.Thread(target=pk_onoff_control_loop_with_diagnostics)
    pk_onoff_thread.daemon = True
    pk_onoff_thread.start()

    bhkw_onoff_thread = threading.Thread(target=bhkw_onoff_control_loop_with_diagnostics)
    bhkw_onoff_thread.daemon = True
    bhkw_onoff_thread.start()

    feed_121517_thread = threading.Thread(target=feed_121517_control_loop_with_diagnostics)
    feed_121517_thread.daemon = True
    feed_121517_thread.start()

if __name__ == '__main__':
    start_control_loops()
    app.run(host='localhost', port=5000)

