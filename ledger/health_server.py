from flask import Flask, jsonify
import os
import psutil

app = Flask(__name__)

@app.route('/healthz')
def healthz():
    # Basic health check: process running, CPU and memory within limits
    pid = os.getpid()
    proc = psutil.Process(pid)
    cpu = proc.cpu_percent(interval=0.1)
    mem = proc.memory_percent()
    status = {
        'pid': pid,
        'alive': proc.is_running(),
        'cpu_percent': cpu,
        'memory_percent': mem,
        'status': 'OK' if cpu < 80 and mem < 80 else 'WARN'
    }
    return jsonify(status)

if __name__ == '__main__':
    port = int(os.getenv('V91_HEALTH_PORT', '9091'))
    app.run(host='0.0.0.0', port=port)
