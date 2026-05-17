import base64
import os
import sys
from io import BytesIO
from pathlib import Path

import requests
from openai import OpenAI
from PIL import Image
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QPixmap, QFont
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QGroupBox, QLabel, QLineEdit, QTextEdit,
    QPushButton, QComboBox, QSpinBox, QProgressBar,
    QMessageBox, QFileDialog, QScrollArea, QSplitter,
)


OUTPUT_DIR = Path(__file__).parent / "output"


def _save_image_from_b64(b64_str: str, save_path: Path):
    image_bytes = base64.b64decode(b64_str)
    save_path.write_bytes(image_bytes)


def _save_image_from_url(url: str, save_path: Path):
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    save_path.write_bytes(resp.content)


SIZE_OPTIONS = [
    "1024x1024", "1024x1536", "1536x1024",
    "2000x1000", "1000x2000", "2000x667", "667x2000",
]
QUALITY_OPTIONS = ["high", "standard"]
THINKING_OPTIONS = ["", "off", "low", "medium", "high"]
BG_OPTIONS = ["", "auto", "transparent", "opaque"]
FORMAT_OPTIONS = ["b64_json", "url"]
MODEL_OPTIONS = ["gpt-image-2", "gpt-image-1", "gpt-image-1-mini", "dall-e-3"]


class GenerateWorker(QThread):
    log_signal = pyqtSignal(str)
    preview_signal = pyqtSignal(list)
    error_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()

    def __init__(self, client_kwargs: dict, params: dict, output_dir: Path, prefix: str):
        super().__init__()
        self._client_kwargs = client_kwargs
        self._params = params
        self._output_dir = output_dir
        self._prefix = prefix

    def run(self):
        try:
            model = self._params["model"]
            size = self._params.get("size", "")
            quality = self._params.get("quality", "")
            count = self._params.get("n", 1)
            prompt = self._params.get("prompt", "")
            response_format = self._params.get("response_format", "b64_json")
            thinking = self._params.get("thinking", "")

            client = OpenAI(**self._client_kwargs)

            self.log_signal.emit(f"[请求] 模型={model}  尺寸={size}  质量={quality}  数量={count}")
            if thinking:
                self.log_signal.emit(f"[请求] 推理模式={thinking}")
            self.log_signal.emit(
                f"[提示] {prompt[:120]}{'…' if len(prompt) > 120 else ''}"
            )

            response = client.images.generate(**self._params)

            self._output_dir.mkdir(parents=True, exist_ok=True)
            saved_paths: list[Path] = []

            for i, image_data in enumerate(response.data):
                filename = f"{self._prefix}_{i + 1:02d}.png"
                save_path = self._output_dir / filename

                if response_format == "b64_json":
                    _save_image_from_b64(image_data.b64_json, save_path)
                else:
                    _save_image_from_url(image_data.url, save_path)

                saved_paths.append(save_path)

            self.log_signal.emit(f"[完成] 成功生成 {len(saved_paths)} 张图像")
            for p in saved_paths:
                self.log_signal.emit(f"       {p}")

            self.preview_signal.emit(saved_paths)

        except Exception as e:
            self.error_signal.emit(str(e))
        finally:
            self.finished_signal.emit()


class ImagePreviewWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QGridLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._labels: list[QLabel] = []
        self._pixmaps: list[QPixmap] = []
        self._row = 0
        self._col = 0

    def clear(self):
        for lb in self._labels:
            lb.deleteLater()
        self._labels.clear()
        self._pixmaps.clear()
        self._row = 0
        self._col = 0

    def add_image(self, image_path: Path, max_size=200):
        img = Image.open(image_path)
        w, h = img.size
        ratio = min(max_size / w, max_size / h)
        new_size = (int(w * ratio), int(h * ratio))
        thumb_img = img.resize(new_size, Image.LANCZOS)

        buf = BytesIO()
        thumb_img.save(buf, format="PNG")
        buf.seek(0)

        pixmap = QPixmap()
        pixmap.loadFromData(buf.read())
        self._pixmaps.append(pixmap)

        lb = QLabel()
        lb.setPixmap(pixmap)
        lb.setFixedSize(pixmap.width(), pixmap.height())
        lb.setStyleSheet("border: 1px solid #ccc;")
        self._layout.addWidget(lb, self._row, self._col)
        self._labels.append(lb)

        self._col += 1
        if self._col >= 3:
            self._col = 0
            self._row += 1


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GPT-Image-2 文生图工具")
        self.setGeometry(100, 100, 960, 780)
        self.setMinimumSize(860, 700)

        self._default_prompt = "一只橘猫坐在窗台上晒太阳，水彩画风格，温暖的午后光线，高细节"
        self._generated_images: list[Path] = []
        self._worker: GenerateWorker | None = None

        self._build_ui()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(8, 8, 8, 8)

        splitter = QSplitter(Qt.Horizontal)

        left_widget = QWidget()
        self._build_left_panel(left_widget)
        splitter.addWidget(left_widget)

        right_widget = QWidget()
        self._build_right_panel(right_widget)
        splitter.addWidget(right_widget)

        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)

        root_layout.addWidget(splitter)

    def _build_left_panel(self, parent: QWidget):
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(4, 4, 4, 4)

        layout.addWidget(self._build_api_group())
        layout.addWidget(self._build_param_group())
        layout.addWidget(self._build_output_group())
        layout.addLayout(self._build_button_bar())
        layout.addStretch()

    def _build_api_group(self) -> QGroupBox:
        group = QGroupBox("API 配置")
        grid = QGridLayout(group)
        grid.setContentsMargins(8, 12, 8, 8)
        grid.setSpacing(6)

        grid.addWidget(QLabel("API Key:"), 0, 0)
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        self.api_key_edit.setPlaceholderText("输入你的 API Key……")
        grid.addWidget(self.api_key_edit, 0, 1)

        self._toggle_key_btn = QPushButton("👁")
        self._toggle_key_btn.setFixedWidth(32)
        self._toggle_key_btn.clicked.connect(self._toggle_api_key_visibility)
        grid.addWidget(self._toggle_key_btn, 0, 2)

        grid.addWidget(QLabel("Base URL:"), 1, 0)
        self.base_url_edit = QLineEdit()
        self.base_url_edit.setPlaceholderText("自定义 API 地址（可选）……")
        grid.addWidget(self.base_url_edit, 1, 1, 1, 2)

        grid.addWidget(QLabel("模型:"), 2, 0)
        self.model_combo = QComboBox()
        self.model_combo.addItems(MODEL_OPTIONS)
        grid.addWidget(self.model_combo, 2, 1, 1, 2)

        grid.addWidget(QLabel("提示词 (Prompt):"), 3, 0, 1, 3)
        self.prompt_edit = QTextEdit()
        self.prompt_edit.setPlaceholderText("输入你的图像描述……")
        self.prompt_edit.setPlainText(self._default_prompt)
        self.prompt_edit.setMaximumHeight(100)
        font = QFont("Microsoft YaHei", 10)
        self.prompt_edit.setFont(font)
        grid.addWidget(self.prompt_edit, 4, 0, 1, 3)

        return group

    def _build_param_group(self) -> QGroupBox:
        group = QGroupBox("生成参数")
        grid = QGridLayout(group)
        grid.setContentsMargins(8, 12, 8, 8)
        grid.setSpacing(6)

        grid.addWidget(QLabel("尺寸:"), 0, 0)
        self.size_combo = QComboBox()
        self.size_combo.addItems(SIZE_OPTIONS)
        grid.addWidget(self.size_combo, 0, 1)

        grid.addWidget(QLabel("质量:"), 0, 2)
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(QUALITY_OPTIONS)
        grid.addWidget(self.quality_combo, 0, 3)

        grid.addWidget(QLabel("数量:"), 1, 0)
        self.count_spin = QSpinBox()
        self.count_spin.setRange(1, 10)
        self.count_spin.setValue(1)
        grid.addWidget(self.count_spin, 1, 1)

        grid.addWidget(QLabel("推理模式:"), 1, 2)
        self.thinking_combo = QComboBox()
        self.thinking_combo.addItems(THINKING_OPTIONS)
        grid.addWidget(self.thinking_combo, 1, 3)

        grid.addWidget(QLabel("背景:"), 2, 0)
        self.bg_combo = QComboBox()
        self.bg_combo.addItems(BG_OPTIONS)
        grid.addWidget(self.bg_combo, 2, 1)

        grid.addWidget(QLabel("种子:"), 2, 2)
        self.seed_edit = QLineEdit()
        self.seed_edit.setPlaceholderText("留空 = 随机")
        grid.addWidget(self.seed_edit, 2, 3)

        grid.addWidget(QLabel("输出格式:"), 3, 0)
        self.format_combo = QComboBox()
        self.format_combo.addItems(FORMAT_OPTIONS)
        grid.addWidget(self.format_combo, 3, 1)

        return group

    def _build_output_group(self) -> QGroupBox:
        group = QGroupBox("输出设置")
        grid = QGridLayout(group)
        grid.setContentsMargins(8, 12, 8, 8)
        grid.setSpacing(6)

        grid.addWidget(QLabel("保存到:"), 0, 0)
        self.output_edit = QLineEdit()
        self.output_edit.setText(str(OUTPUT_DIR.resolve()))
        grid.addWidget(self.output_edit, 0, 1)

        browse_btn = QPushButton("浏览…")
        browse_btn.clicked.connect(self._browse_output)
        grid.addWidget(browse_btn, 0, 2)

        grid.addWidget(QLabel("文件名前缀:"), 1, 0)
        self.prefix_edit = QLineEdit()
        self.prefix_edit.setText("gpt-image")
        grid.addWidget(self.prefix_edit, 1, 1)

        return group

    def _build_button_bar(self) -> QHBoxLayout:
        bar = QHBoxLayout()
        bar.setSpacing(8)

        self.generate_btn = QPushButton("🚀 生成图像")
        self.generate_btn.setFont(QFont("Microsoft YaHei", 11, QFont.Bold))
        self.generate_btn.setStyleSheet(
            "QPushButton { background-color: #4A90D9; color: white; padding: 6px 20px; "
            "border: none; border-radius: 4px; }"
            "QPushButton:hover { background-color: #357ABD; }"
            "QPushButton:disabled { background-color: #A0C4E8; }"
        )
        self.generate_btn.clicked.connect(self._generate)
        bar.addWidget(self.generate_btn)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(20)
        bar.addWidget(self.progress_bar, 1)

        return bar

    def _build_right_panel(self, parent: QWidget):
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(4, 4, 4, 4)

        log_group = QGroupBox("运行日志")
        log_layout = QVBoxLayout(log_group)
        self.log_edit = QTextEdit()
        self.log_edit.setReadOnly(True)
        font = QFont("Consolas", 9)
        self.log_edit.setFont(font)
        log_layout.addWidget(self.log_edit)
        layout.addWidget(log_group, 1)

        preview_group = QGroupBox("生成预览")
        preview_layout = QVBoxLayout(preview_group)
        preview_layout.setContentsMargins(0, 0, 0, 0)

        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll_area.setStyleSheet("QScrollArea { border: none; }")

        self.preview_container = ImagePreviewWidget()
        self._scroll_area.setWidget(self.preview_container)

        preview_layout.addWidget(self._scroll_area)
        layout.addWidget(preview_group, 2)

        clear_btn = QPushButton("清空预览")
        clear_btn.clicked.connect(self._clear_preview)
        layout.addWidget(clear_btn, 0, Qt.AlignRight)

    def _toggle_api_key_visibility(self):
        if self.api_key_edit.echoMode() == QLineEdit.Password:
            self.api_key_edit.setEchoMode(QLineEdit.Normal)
            self._toggle_key_btn.setText("🙈")
        else:
            self.api_key_edit.setEchoMode(QLineEdit.Password)
            self._toggle_key_btn.setText("👁")

    def _browse_output(self):
        path = QFileDialog.getExistingDirectory(
            self, "选择输出目录", self.output_edit.text()
        )
        if path:
            self.output_edit.setText(path)

    def _clear_preview(self):
        self.preview_container.clear()
        self._generated_images.clear()

    def _log(self, msg: str):
        self.log_edit.append(msg)

    def _generate(self):
        api_key = self.api_key_edit.text().strip() or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            QMessageBox.critical(
                self, "错误",
                "请在 API 配置中填写 API Key，或设置环境变量 OPENAI_API_KEY"
            )
            return

        prompt = self.prompt_edit.toPlainText().strip()
        if not prompt:
            QMessageBox.critical(self, "错误", "请输入提示词")
            return

        self.generate_btn.setEnabled(False)
        self.generate_btn.setText("⏳ 生成中…")
        self.progress_bar.setVisible(True)

        model = self.model_combo.currentText()
        size = self.size_combo.currentText()
        quality = self.quality_combo.currentText()
        count = self.count_spin.value()
        response_format = self.format_combo.currentText()
        output_dir = Path(self.output_edit.text())
        prefix = self.prefix_edit.text().strip() or "gpt-image"

        client_kwargs = {"api_key": api_key}
        base_url = self.base_url_edit.text().strip()
        if base_url:
            client_kwargs["base_url"] = base_url

        params = {
            "model": model,
            "prompt": prompt,
            "n": count,
            "size": size,
            "quality": quality,
            "response_format": response_format,
        }

        thinking = self.thinking_combo.currentText()
        if thinking:
            params["thinking"] = thinking

        bg = self.bg_combo.currentText()
        if bg:
            params["background"] = bg

        seed_raw = self.seed_edit.text().strip()
        if seed_raw:
            params["seed"] = int(seed_raw)

        self._worker = GenerateWorker(client_kwargs, params, output_dir, prefix)
        self._worker.log_signal.connect(self._log)
        self._worker.preview_signal.connect(self._show_previews)
        self._worker.error_signal.connect(self._on_error)
        self._worker.finished_signal.connect(self._finish_generate)
        self._worker.start()

    def _show_previews(self, paths: list[Path]):
        for p in paths:
            try:
                self.preview_container.add_image(p)
            except Exception as e:
                self._log(f"[预览] 加载失败: {p.name} - {e}")
        self._generated_images.extend(paths)

    def _on_error(self, msg: str):
        self._log(f"[错误] {msg}")
        QMessageBox.critical(self, "生成失败", msg)

    def _finish_generate(self):
        self.progress_bar.setVisible(False)
        self.generate_btn.setEnabled(True)
        self.generate_btn.setText("🚀 生成图像")


def _fix_qt_plugin_path():
    import PyQt5
    plugin_path = (
        Path(PyQt5.__file__).parent / "Qt5" / "plugins"
    )
    if plugin_path.is_dir():
        os.environ.setdefault("QT_QPA_PLATFORM_PLUGIN_PATH", str(plugin_path.resolve()))


def main():
    _fix_qt_plugin_path()
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()