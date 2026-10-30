#!/usr/bin/env python3
"""GPU Unlock — Port Scanner (PySide6 QThread + socket.connect_ex).
Phase 1 verified: PySide6 6.12.0 QtWidgets (QApplication, QMainWindow, QLineEdit,
QPushButton, QTableWidget, QProgressBar, QVBoxLayout, QHBoxLayout, QHeaderView);
QtGui.QPalette; QTableWidgetItem.setBackground/foreground; QThread+Signal;
socket.connect_ex returns 0 on success; QFileDialog.getSaveFileName;
os.path.expanduser("~/Desktop"). Scapy NOT installed → raw socket only."""
import csv, os, socket, sys
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (QApplication, QHBoxLayout, QLabel, QLineEdit, QMainWindow,
    QPushButton, QProgressBar, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget, QFileDialog, QHeaderView)

S, SC, A, T, G, Y, R = "#0d0d0d", "#1a1a1a", "#00ff88", "#e6e6e6", "#8a8a8a", "#ffd23f", "#ff4d4d"
SVC = {22:"ssh",21:"ftp",23:"telnet",25:"smtp",53:"dns",80:"http",110:"pop3",143:"imap",443:"https",
       993:"imaps",995:"pop3s",3306:"mysql",5432:"postgresql",6379:"redis",27017:"mongodb",8080:"http-proxy",3000:"dev"}
STYLESHEET = f"""
QWidget {{ font-family: "Segoe UI", sans-serif; font-size: 12px; color: {T}; }}
QLineEdit {{ background: {SC}; border: 1px solid #2e2e2e; border-radius: 6px; padding: 4px 8px; }}
QPushButton {{ background: {A}; color: #000; border: none; border-radius: 6px; padding: 6px 14px; font-weight: 700; }}
QPushButton:hover {{ background: #33ffa0; }}
QPushButton#secondary {{ background: {SC}; color: {T}; border: 1px solid #2e2e2e; }}
QLabel#status {{ color: {G}; font-size: 10px; }}
QTableWidget {{ background: {SC}; alternate-background-color: #141414; border: none; }}
QHeaderView::section {{ background: {SC}; color: {G}; border: none; padding: 4px 8px; font-size: 11px; font-weight: 600; }}
QProgressBar {{ text-align: center; font-size: 11px; color: {T}; }}
QProgressBar::chunk {{ background: {A}; border-radius: 3px; }}
"""
_ROLES = [(QPalette.ColorRole.Window, S), (QPalette.ColorRole.WindowText, T),
          (QPalette.ColorRole.Button, SC), (QPalette.ColorRole.ButtonText, T),
          (QPalette.ColorRole.BrightText, A), (QPalette.ColorRole.Text, G)]
_ROW_COLORS = {0: (QColor("#00cc6e"), QColor("#000")), 1: (QColor(R), QColor("#fff")), 2: (QColor(Y), QColor("#000"))}

def _range(r):
    if "-" in r:
        p = r.split("-"); s, e = int(p[0]), int(p[1])
    else:
        s = e = int(r)
    if not 1 <= s <= 65535 or not 1 <= e <= 65535 or s > e:
        raise ValueError
    return s, e

def _scan(host, port):
    """connect_ex: 0=OPEN, 10061/111=CLOSED, else=FILTERED."""
    sk = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        r = sk.connect_ex((host, port))
        if r == 0:
            try: svc = socket.getservbyport(port, "tcp")
            except OSError: svc = SVC.get(port, "unknown")
            return 0, "OPEN", svc
        return (1, "CLOSED", "—") if r in (10061, 111) else (2, "FILTERED", "—")
    except Exception:
        return 2, "FILTERED", "—"
    finally:
        sk.close()

class PortScannerWorker(QThread):
    progress = Signal(int, int, int, int)
    finished = Signal(int, int, int, int)
    port_result = Signal(int, int, str, str)
    def __init__(self, host, port_range):
        super().__init__()
        self.host, self.port_range, self._abort = host, port_range, False
    def run(self):
        try: start, end = _range(self.port_range)
        except ValueError:
            self.finished.emit(0, 0, 0, 0); return
        count = oc = cc = fc = 0
        for port in range(start, end + 1):
            if self._abort: break
            state, ss, svc = _scan(self.host, port)
            count += 1
            if state == 0: oc += 1
            elif state == 1: cc += 1
            else: fc += 1
            self.port_result.emit(port, state, ss, svc)
            self.progress.emit(count, oc, cc, fc)
        self.finished.emit(end - start + 1, oc, cc, fc)
    def abort(self): self._abort = True

class ScannerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GPU Unlock — Port Scanner")
        self.setFixedSize(550, 420)
        self._worker = None
        self._build_ui()
    def _build_ui(self):
        pal = QPalette()
        for role, color in _ROLES: pal.setColor(role, QColor(color))
        self.setPalette(pal); self.setStyleSheet(STYLESHEET)
        root = QWidget()
        lay = QVBoxLayout(root)
        lay.setContentsMargins(16, 16, 16, 16); lay.setSpacing(10)
        top = QHBoxLayout()
        self.ip_input = QLineEdit("127.0.0.1"); self.port_input = QLineEdit("1-1024")
        self.port_input.setMaxLength(13)
        scan_btn = QPushButton("Scan"); export_btn = QPushButton("Export CSV")
        export_btn.setObjectName("secondary")
        for w in (self.ip_input, self.port_input, scan_btn, export_btn): w.setFixedHeight(28)
        scan_btn.setFixedWidth(80); export_btn.setFixedWidth(90)
        top.addWidget(QLabel("Host:")); top.addWidget(self.ip_input, 1)
        top.addWidget(QLabel("Ports:")); top.addWidget(self.port_input, 1)
        top.addWidget(scan_btn); top.addWidget(export_btn)
        lay.addLayout(top)
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Port", "State", "Service"])
        self.table.setSortingEnabled(True)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.Stretch)
        lay.addWidget(self.table, 1)
        self.progress = QProgressBar(); self.progress.setFixedHeight(16)
        self.status_lbl = QLabel("Ready — enter a host and port range, then click Scan.")
        self.status_lbl.setObjectName("status")
        bottom = QHBoxLayout()
        bottom.addWidget(self.progress, 1); bottom.addWidget(self.status_lbl)
        lay.addLayout(bottom)
        self.setCentralWidget(root)
        scan_btn.clicked.connect(self._on_scan)
        export_btn.clicked.connect(self._on_export)
    def _on_scan(self):
        if self._worker and self._worker.isRunning():
            self._worker.abort(); self._worker = None
            self.status_lbl.setText("Scan aborted."); return
        host = self.ip_input.text().strip()
        pr = self.port_input.text().strip()
        if not host:
            self.status_lbl.setText("Enter a host IP."); return
        try: start, end = _range(pr)
        except ValueError:
            self.status_lbl.setText("Invalid port range. Use 1-1024."); return
        self.table.setRowCount(0); self.progress.setValue(0)
        self.progress.setMaximum(end - start + 1)
        self._worker = PortScannerWorker(host, pr)
        self._worker.progress.connect(self._on_progress)
        self._worker.port_result.connect(self._on_port_result)
        self._worker.finished.connect(self._on_scan_finished)
        self._worker.start()
        self.status_lbl.setText(f"Scanning {host} ports {start}-{end}...")
    def _on_progress(self, count, oc, cc, fc):
        self.progress.setValue(count)
        self.status_lbl.setText(f"Scanned {count} — {oc} open, {cc} closed, {fc} filtered")
    def _on_port_result(self, port, state_int, state_str, service):
        row = self.table.rowCount(); self.table.insertRow(row)
        pi = QTableWidgetItem(str(port)); pi.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        si = QTableWidgetItem(state_str); si.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        bg, fg = _ROW_COLORS.get(state_int, (QColor(G), QColor(T)))
        si.setBackground(bg); si.setForeground(fg)
        self.table.setItem(row, 0, pi); self.table.setItem(row, 1, si)
        self.table.setItem(row, 2, QTableWidgetItem(service))
    def _on_scan_finished(self, total, oc, cc, fc):
        self.status_lbl.setText(f"Done — {oc} open, {cc} closed, {fc} filtered (of {total} scanned)")
        self.progress.setValue(0)
    def _on_export(self):
        if self.table.rowCount() == 0:
            self.status_lbl.setText("No results to export."); return
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        path, _ = QFileDialog.getSaveFileName(self, "Save CSV", desktop, "CSV Files (*.csv)")
        if not path: return
        try:
            with open(path, "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["Port", "State", "Service"])
                for row in range(self.table.rowCount()):
                    w.writerow([self.table.item(row, c).text() if self.table.item(row, c) else "" for c in range(3)])
            self.status_lbl.setText(f"Exported {self.table.rowCount()} rows")
        except Exception as e:
            self.status_lbl.setText(f"Export failed: {e}")

def main():
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("GPU Unlock Scanner")
    w = ScannerWindow(); w.show()
    return app.exec()

if __name__ == "__main__":
    sys.exit(main())
# --------------------------------------------------------------------------- #
# How to verify
# --------------------------------------------------------------------------- #
# This scanner uses socket.connect_ex() — compare results with Nmap/Zenmap:
#   1. Nmap: nmap -sT -p 1-1024 <target> --open
#   2. Wireshark: filter "tcp.port >= 1 && tcp.port <= 1024"
#      → open: SYN+SYN-ACK | closed: SYN+RST-ACK | filtered: SYN only
#   3. Disagreements: this scanner uses full connect() (like nmap -sT, not -sS);
#      nmap -sS may mark open ports as "filtered"; firewalls dropping SYN without
#      RST → FILTERED by both; cross-check: ss -tlnp (Linux) or netstat -an (Win)

# --------------------------------------------------------------------------- #
# Why this works
# --------------------------------------------------------------------------- #
# Why connect_ex over connect: connect() raises on every failure (ConnectionRefused,
#   timeout). connect_ex() returns errno — 0=success, 10061/111=refused, else=filtered.
# Why QThread over threading.Thread: QThread Signals are delivered to the main thread's
#   event loop — scan results update QTableWidget directly, no manual marshaling.
#   threading.Thread would need invokeMethod or queues to update GUI safely.
# What breaks if you scan all 65535 ports:
#   1. Performance: 65535×0.5s ≈ 9h. Fix: use nmap via subprocess.
#   2. Memory: each port→QTableWidgetItem (~100+ MB at 65535). Fix: model/view + pagination.
#   3. Firewall/AV alerts: mass scanning triggers endpoint protection. Fix: rate-limit.
#   4. Ephemeral port exhaustion: rapid connect/close. Fix: close in finally + SO_REUSEADDR.
