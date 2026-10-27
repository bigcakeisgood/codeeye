"""CodeEye: webcam barcode scanner and code generator."""
import json
import sys
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import qrcode
import zxingcpp
from PIL import Image, ImageQt
from PyQt6.QtCore import Qt, QTimer, QRect
from PyQt6.QtGui import QImage, QPixmap, QColor
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton, QComboBox,
    QLineEdit, QTextEdit, QFileDialog, QMessageBox, QVBoxLayout, QHBoxLayout,
    QFormLayout, QSpinBox, QSlider, QTabWidget, QListWidget, QListWidgetItem,
    QCheckBox, QGroupBox, QRubberBand, QSplitter
)

APP_DIR = Path.home() / ".codeeye"
HISTORY_FILE = APP_DIR / "history.json"
APP_DIR.mkdir(parents=True, exist_ok=True)


class VideoLabel(QLabel):
    """Video surface with a draggable ROI selection."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(480, 320)
        self.setStyleSheet("background:#111827;color:#9ca3af;border-radius:12px;")
        self.rubber = QRubberBand(QRubberBand.Shape.Rectangle, self)
        self.origin = None
        self.roi_rect = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.origin = event.position().toPoint()
            self.rubber.setGeometry(QRect(self.origin, self.origin))
            self.rubber.show()

    def mouseMoveEvent(self, event):
        if self.origin is not None:
            self.rubber.setGeometry(QRect(self.origin, event.position().toPoint()).normalized())

    def mouseReleaseEvent(self, event):
        if self.origin is not None:
            rect = QRect(self.origin, event.position().toPoint()).normalized()
            self.roi_rect = rect if rect.width() > 12 and rect.height() > 12 else None
            self.rubber.hide()
            self.origin = None
            self.parent().parent().roi_changed()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CodeEye — Scan & Generate")
        self.resize(1120, 760)
        self.cap = None
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)
        self.last_frame = None
        self.zoom = 1.0
        self.roi = None
        self.seen = set()
        self.history = self.load_history()
        self.build_ui()
        self.refresh_history()
        self.setStyleSheet("""
            QMainWindow,QWidget { background:#f5f7fb; color:#172033; font-size:13px; }
            QGroupBox { border:1px solid #dbe2ee; border-radius:10px; margin-top:12px;
                        padding:12px; font-weight:600; }
            QGroupBox::title { subcontrol-origin:margin; left:12px; padding:0 5px; }
            QPushButton { background:#315efb; color:white; border:0; border-radius:7px;
                          padding:9px 13px; font-weight:600; }
            QPushButton:hover { background:#2449ce; }
            QPushButton:disabled { background:#9ca8c2; }
            QLineEdit,QTextEdit,QComboBox,QSpinBox,QListWidget {
                background:white; border:1px solid #d6deeb; border-radius:6px; padding:7px;
            }
            QTabWidget::pane { border:1px solid #dbe2ee; border-radius:9px; }
            QTabBar::tab { padding:10px 18px; background:#e9edf5; border-radius:6px; }
            QTabBar::tab:selected { background:#315efb; color:white; }
        """)

    def build_ui(self):
        root = QWidget()
        outer = QVBoxLayout(root)
        header = QHBoxLayout()
        brand = QLabel("◉  CodeEye")
        brand.setStyleSheet("font-size:25px;font-weight:800;color:#2449ce;")
        subtitle = QLabel("Camera scanner  •  barcode studio")
        subtitle.setStyleSheet("color:#64748b;")
        header.addWidget(brand)
        header.addSpacing(14)
        header.addWidget(subtitle)
        header.addStretch()
        self.status = QLabel("Camera stopped")
        self.status.setStyleSheet("color:#64748b;")
        header.addWidget(self.status)
        outer.addLayout(header)

        self.tabs = QTabWidget()
        outer.addWidget(self.tabs)
        self.tabs.addTab(self.make_scanner_tab(), "⌕  Scan")
        self.tabs.addTab(self.make_generator_tab(), "▦  Generate")
        self.tabs.addTab(self.make_history_tab(), "◷  History")
        self.setCentralWidget(root)

    def make_scanner_tab(self):
        tab = QWidget()
        layout = QHBoxLayout(tab)
        left = QVBoxLayout()
        self.video = VideoLabel(self)
        # The label's parent chain is not used for ROI handling; connect through a callback.
        self.video.parent_window = self
        self.video.mouseReleaseEvent = self.video_release
        left.addWidget(self.video, 1)
        buttons = QHBoxLayout()
        self.start_btn = QPushButton("Start camera")
        self.start_btn.clicked.connect(self.toggle_camera)
        self.snapshot_btn = QPushButton("Scan image…")
        self.snapshot_btn.clicked.connect(self.scan_file)
        self.clear_roi_btn = QPushButton("Clear crop")
        self.clear_roi_btn.clicked.connect(self.clear_roi)
        buttons.addWidget(self.start_btn)
        buttons.addWidget(self.snapshot_btn)
        buttons.addWidget(self.clear_roi_btn)
        left.addLayout(buttons)
        layout.addLayout(left, 3)

        side = QVBoxLayout()
        controls = QGroupBox("Camera controls")
        form = QFormLayout(controls)
        self.camera_select = QComboBox()
        self.camera_select.addItems(["Camera 0", "Camera 1", "Camera 2", "Camera 3"])
        form.addRow("Device", self.camera_select)
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(10, 40)
        self.zoom_slider.setValue(10)
        self.zoom_slider.valueChanged.connect(self.set_zoom)
        form.addRow("Zoom", self.zoom_slider)
        self.flash = QCheckBox("Brighten side panel (screen fill light)")
        self.flash.toggled.connect(self.set_flash)
        form.addRow(self.flash)
        self.crop_check = QCheckBox("Limit scanning to crop")
        self.crop_check.setChecked(True)
        form.addRow(self.crop_check)
        self.scan_formats = QComboBox()
        self.scan_formats.addItems(["All supported formats", "QR Code", "Aztec", "Codabar",
                                    "Code 39", "Code 93", "Code 128", "Data Matrix",
                                    "EAN-8", "EAN-13", "ITF", "PDF417", "UPC-A", "UPC-E"])
        form.addRow("Format filter", self.scan_formats)
        side.addWidget(controls)

        self.result_box = QTextEdit()
        self.result_box.setReadOnly(True)
        self.result_box.setPlaceholderText("Decoded text will appear here…")
        side.addWidget(QLabel("Latest result"))
        side.addWidget(self.result_box, 1)
        self.flash_panel = QLabel("LIGHT")
        self.flash_panel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.flash_panel.setMinimumHeight(45)
        self.flash_panel.setStyleSheet("background:#fff3b0;color:#7c5b00;border-radius:8px;font-weight:800;")
        self.flash_panel.hide()
        side.addWidget(self.flash_panel)
        layout.addLayout(side, 2)
        return tab

    def make_generator_tab(self):
        tab = QWidget()
        layout = QHBoxLayout(tab)
        controls = QVBoxLayout()
        group = QGroupBox("Code settings")
        form = QFormLayout(group)
        self.gen_format = QComboBox()
        self.gen_format.addItems(["QR Code", "Code 128", "Code 39", "EAN-13", "EAN-8", "ITF"])
        form.addRow("Format", self.gen_format)
        self.gen_text = QLineEdit()
        self.gen_text.setPlaceholderText("Enter text, URL, or code data")
        form.addRow("Content", self.gen_text)
        self.ec_level = QComboBox()
        self.ec_level.addItems(["L — 7%", "M — 15%", "Q — 25%", "H — 30%"])
        form.addRow("QR error correction", self.ec_level)
        self.quiet_zone = QSpinBox()
        self.quiet_zone.setRange(0, 30)
        self.quiet_zone.setValue(4)
        self.quiet_zone.setSuffix(" modules / units")
        form.addRow("Quiet zone", self.quiet_zone)
        self.box_size = QSpinBox()
        self.box_size.setRange(2, 20)
        self.box_size.setValue(8)
        form.addRow("Module size", self.box_size)
        self.foreground = QLineEdit("#111111")
        form.addRow("Foreground color", self.foreground)
        self.background = QLineEdit("#ffffff")
        form.addRow("Background color", self.background)
        controls.addWidget(group)
        generate = QPushButton("Generate code")
        generate.clicked.connect(self.generate_code)
        controls.addWidget(generate)
        save = QPushButton("Save image…")
        save.clicked.connect(self.save_generated)
        controls.addWidget(save)
        controls.addStretch()
        note = QLabel("QR codes support L / M / Q / H correction. Linear barcode formats use python-barcode.")
        note.setWordWrap(True)
        note.setStyleSheet("color:#64748b;")
        controls.addWidget(note)
        layout.addLayout(controls, 2)
        self.generated_preview = QLabel("Your code preview appears here")
        self.generated_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.generated_preview.setMinimumSize(350, 350)
        self.generated_preview.setStyleSheet("background:white;border:1px dashed #cbd5e1;border-radius:12px;")
        layout.addWidget(self.generated_preview, 3)
        self.generated_image = None
        return tab

    def make_history_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        row = QHBoxLayout()
        row.addWidget(QLabel("Scan and generation history is stored locally on this computer."))
        row.addStretch()
        clear = QPushButton("Clear history")
        clear.clicked.connect(self.clear_history)
        row.addWidget(clear)
        layout.addLayout(row)
        self.history_list = QListWidget()
        self.history_list.itemDoubleClicked.connect(self.copy_history_item)
        layout.addWidget(self.history_list)
        return tab

    def toggle_camera(self):
        if self.cap is not None:
            self.timer.stop()
            self.cap.release()
            self.cap = None
            self.start_btn.setText("Start camera")
            self.status.setText("Camera stopped")
            return
        device = self.camera_select.currentIndex()
        self.cap = cv2.VideoCapture(device)
        if not self.cap.isOpened():
            self.cap.release()
            self.cap = None
            QMessageBox.warning(self, "Camera unavailable", "Could not open this camera. Check permissions or select another device.")
            return
        self.timer.start(35)
        self.start_btn.setText("Stop camera")
        self.status.setText("Camera running")

    def update_frame(self):
        if self.cap is None:
            return
        ok, frame = self.cap.read()
        if not ok:
            self.status.setText("No camera frame")
            return
        frame = cv2.flip(frame, 1)
        self.last_frame = frame
        shown = self.apply_zoom(frame)
        if self.video.roi_rect:
            # Selection rectangle is widget-relative and is only a visual guide.
            pass
        rgb = cv2.cvtColor(shown, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qimg = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888).copy()
        self.video.setPixmap(QPixmap.fromImage(qimg).scaled(
            self.video.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        self.try_decode(frame)

    def apply_zoom(self, frame):
        if self.zoom <= 1.01:
            return frame
        h, w = frame.shape[:2]
        nw, nh = int(w / self.zoom), int(h / self.zoom)
        x, y = (w - nw) // 2, (h - nh) // 2
        return cv2.resize(frame[y:y+nh, x:x+nw], (w, h), interpolation=cv2.INTER_LINEAR)

    def set_zoom(self, value):
        self.zoom = value / 10.0

    def set_flash(self, enabled):
        self.flash_panel.setVisible(enabled)
        if enabled:
            self.flash_panel.setText("◉  LIGHT ON  —  screen brightness")
            self.status.setText("Screen fill light enabled")
        else:
            self.status.setText("Camera running" if self.cap else "Camera stopped")

    def video_release(self, event):
        # Convert drag selection on the displayed video into a frame-space crop.
        if event.button() == Qt.MouseButton.LeftButton and self.video.origin is not None:
            rect = QRect(self.video.origin, event.position().toPoint()).normalized()
            self.video.roi_rect = rect if rect.width() > 12 and rect.height() > 12 else None
            self.video.rubber.hide()
            self.video.origin = None
            self.roi_changed()

    def roi_changed(self):
        self.status.setText("Crop selected — scan is limited to selection" if self.video.roi_rect else "Crop cleared")

    def clear_roi(self):
        self.video.roi_rect = None
        self.video.rubber.hide()
        self.status.setText("Crop cleared")

    def crop_frame(self, frame):
        if not self.crop_check.isChecked() or self.video.roi_rect is None:
            return frame
        rect = self.video.roi_rect
        # Map widget coordinates to the actual image, accounting for letterboxing.
        fh, fw = frame.shape[:2]
        vw, vh = self.video.width(), self.video.height()
        scale = min(vw / fw, vh / fh)
        disp_w, disp_h = fw * scale, fh * scale
        ox, oy = (vw - disp_w) / 2, (vh - disp_h) / 2
        x1 = max(0, int((rect.left() - ox) / scale))
        y1 = max(0, int((rect.top() - oy) / scale))
        x2 = min(fw, int((rect.right() - ox) / scale))
        y2 = min(fh, int((rect.bottom() - oy) / scale))
        return frame[y1:y2, x1:x2] if x2 > x1 and y2 > y1 else frame

    def try_decode(self, frame):
        frame = self.crop_frame(frame)
        try:
            results = zxingcpp.read_barcodes(frame)
        except Exception:
            return
        desired = self.scan_formats.currentText()
        for result in results:
            if not result.valid:
                continue
            fmt = str(result.format).replace("BarcodeFormat.", "")
            if desired != "All supported formats" and desired.lower() not in fmt.lower():
                continue
            text = result.text
            key = (fmt, text)
            if key in self.seen:
                continue
            self.seen.add(key)
            self.result_box.setPlainText(f"Format: {fmt}\n\n{text}")
            self.add_history("Scan", fmt, text)

    def scan_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open barcode image", "", "Images (*.png *.jpg *.jpeg *.bmp *.webp)")
        if not path:
            return
        image = cv2.imread(path)
        if image is None:
            QMessageBox.warning(self, "Invalid image", "Could not read that image.")
            return
        results = zxingcpp.read_barcodes(image)
        valid = [r for r in results if r.valid]
        if not valid:
            QMessageBox.information(self, "No code found", "No supported barcode was detected in this image.")
            return
        lines = []
        for r in valid:
            fmt = str(r.format).replace("BarcodeFormat.", "")
            lines.append(f"Format: {fmt}\n{r.text}")
            self.add_history("Image scan", fmt, r.text)
        self.result_box.setPlainText("\n\n".join(lines))

    def generate_code(self):
        data = self.gen_text.text().strip()
        if not data:
            QMessageBox.information(self, "Missing content", "Enter some text or data first.")
            return
        fmt = self.gen_format.currentText()
        try:
            fg = QColor(self.foreground.text())
            bg = QColor(self.background.text())
            if not fg.isValid() or not bg.isValid():
                raise ValueError("Use valid colors such as #111111 and #ffffff.")
            if fmt == "QR Code":
                levels = [qrcode.constants.ERROR_CORRECT_L, qrcode.constants.ERROR_CORRECT_M,
                          qrcode.constants.ERROR_CORRECT_Q, qrcode.constants.ERROR_CORRECT_H]
                qr = qrcode.QRCode(version=None, error_correction=levels[self.ec_level.currentIndex()],
                                   box_size=self.box_size.value(), border=self.quiet_zone.value())
                qr.add_data(data)
                qr.make(fit=True)
                img = qr.make_image(fill_color=fg.name(), back_color=bg.name()).convert("RGB")
            else:
                import barcode
                from barcode.writer import ImageWriter
                names = {"Code 128": "code128", "Code 39": "code39", "EAN-13": "ean13",
                         "EAN-8": "ean8", "ITF": "itf"}
                cls = barcode.get_barcode_class(names[fmt])
                code = cls(data, writer=ImageWriter())
                pil_img = code.render(writer_options={"quiet_zone": self.quiet_zone.value(),
                                                       "module_width": 0.3 * self.box_size.value() / 8,
                                                       "write_text": True,
                                                       "foreground": fg.name(), "background": bg.name()})
                img = pil_img.convert("RGB")
            self.generated_image = img
            qimg = ImageQt.ImageQt(img)
            self.generated_preview.setPixmap(QPixmap.fromImage(qimg).scaled(
                self.generated_preview.size(), Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))
            self.add_history("Generate", fmt, data)
        except Exception as exc:
            QMessageBox.warning(self, "Could not generate", str(exc))

    def save_generated(self):
        if self.generated_image is None:
            QMessageBox.information(self, "Nothing to save", "Generate a code first.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save code image", "codeeye.png",
                                               "PNG image (*.png);;JPEG image (*.jpg)")
        if path:
            self.generated_image.save(path)
            self.status.setText(f"Saved {Path(path).name}")

    def load_history(self):
        try:
            return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []

    def add_history(self, action, fmt, data):
        self.history.insert(0, {"time": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S"),
                                "action": action, "format": fmt, "data": data})
        self.history = self.history[:500]
        try:
            HISTORY_FILE.write_text(json.dumps(self.history, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            pass
        self.refresh_history()

    def refresh_history(self):
        if not hasattr(self, "history_list"):
            return
        self.history_list.clear()
        for item in self.history:
            preview = item["data"].replace("\n", " ")[:90]
            self.history_list.addItem(QListWidgetItem(
                f'{item["time"]}   ·   {item["action"]} / {item["format"]}   ·   {preview}'))

    def copy_history_item(self, item):
        index = self.history_list.row(item)
        if 0 <= index < len(self.history):
            from PyQt6.QtWidgets import QApplication
            QApplication.clipboard().setText(self.history[index]["data"])

    def clear_history(self):
        answer = QMessageBox.question(self, "Clear history", "Delete all local history entries?")
        if answer == QMessageBox.StandardButton.Yes:
            self.history = []
            self.seen.clear()
            HISTORY_FILE.write_text("[]", encoding="utf-8")
            self.refresh_history()

    def closeEvent(self, event):
        self.timer.stop()
        if self.cap is not None:
            self.cap.release()
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("CodeEye")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
