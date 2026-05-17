import os
import sys
import base64
import threading
from pathlib import Path
from tkinter import (
    Tk, Frame, LabelFrame, Label, Entry, Text, Button,
    Spinbox, OptionMenu, StringVar, IntVar, BooleanVar,
    messagebox, filedialog, ttk, scrolledtext, Canvas,
)
from tkinter.font import Font

import requests
from openai import OpenAI
from PIL import Image, ImageTk


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


class ImagePreviewFrame(Frame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.thumbnails: list[ImageTk.PhotoImage] = []
        self.labels: list[Label] = []

    def clear(self):
        for lb in self.labels:
            lb.destroy()
        self.thumbnails.clear()
        self.labels.clear()

    def add_image(self, image_path: Path, max_size=200):
        img = Image.open(image_path)
        w, h = img.size
        ratio = min(max_size / w, max_size / h)
        new_size = (int(w * ratio), int(h * ratio))
        thumb_img = img.resize(new_size, Image.LANCZOS)
        photo = ImageTk.PhotoImage(thumb_img)
        self.thumbnails.append(photo)

        row = len(self.labels) // 3
        col = len(self.labels) % 3
        lb = Label(self, image=photo, borderwidth=1, relief="solid")
        lb.grid(row=row, column=col, padx=6, pady=6, sticky="n")
        self.labels.append(lb)


class App(Tk):
    def __init__(self):
        super().__init__()
        self.title("GPT-Image-2 文生图工具")
        self.geometry("960x780")
        self.minsize(860, 700)

        self._default_prompt = "一只橘猫坐在窗台上晒太阳，水彩画风格，温暖的午后光线，高细节"
        self._generated_images: list[Path] = []

        self._build_ui()

    def _build_ui(self):
        pad = {"padx": 10, "pady": 4}

        main_paned = ttk.PanedWindow(self, orient="horizontal")
        main_paned.pack(fill="both", expand=True, padx=8, pady=8)

        left_frame = ttk.Frame(main_paned)
        right_frame = ttk.Frame(main_paned)
        main_paned.add(left_frame, weight=2)
        main_paned.add(right_frame, weight=1)

        self._build_left_panel(left_frame)
        self._build_right_panel(right_frame)

    def _build_left_panel(self, parent):
        pad = {"padx": 8, "pady": 3}

        api_frame = LabelFrame(parent, text="API 配置")
        api_frame.pack(fill="x", **pad)

        row = 0
        Label(api_frame, text="API Key:").grid(row=row, column=0, sticky="e", padx=(0, 4))
        self.api_key_var = StringVar()
        self.api_key_entry = Entry(api_frame, textvariable=self.api_key_var, width=44, show="*")
        self.api_key_entry.grid(row=row, column=1, sticky="ew", padx=(0, 4))
        self._toggle_key_btn = Button(
            api_frame, text="👁", width=3, command=self._toggle_api_key_visibility
        )
        self._toggle_key_btn.grid(row=row, column=2)
        api_frame.columnconfigure(1, weight=1)

        row += 1
        Label(api_frame, text="Base URL:").grid(row=row, column=0, sticky="e", padx=(0, 4))
        self.base_url_var = StringVar()
        Entry(api_frame, textvariable=self.base_url_var, width=50).grid(
            row=row, column=1, columnspan=2, sticky="ew"
        )

        row += 1
        Label(api_frame, text="模型:").grid(row=row, column=0, sticky="e", padx=(0, 4))
        self.model_var = StringVar(value=MODEL_OPTIONS[0])
        OptionMenu(api_frame, self.model_var, *MODEL_OPTIONS).grid(
            row=row, column=1, sticky="w"
        )

        row += 1
        sep = ttk.Separator(api_frame, orient="horizontal")
        sep.grid(row=row, column=0, columnspan=3, sticky="ew", pady=4)

        row += 1
        lbl = Label(api_frame, text="提示词 (Prompt):")
        lbl.grid(row=row, column=0, columnspan=3, sticky="w")

        row += 1
        self.prompt_text = Text(api_frame, height=5, wrap="word", font=("Microsoft YaHei", 10))
        self.prompt_text.insert("1.0", self._default_prompt)
        self.prompt_text.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(0, 4))
        api_frame.columnconfigure(1, weight=1)

        param_frame = LabelFrame(parent, text="生成参数")
        param_frame.pack(fill="x", **pad)

        r = 0
        Label(param_frame, text="尺寸:").grid(row=r, column=0, sticky="e", padx=(0, 4))
        self.size_var = StringVar(value=SIZE_OPTIONS[0])
        OptionMenu(param_frame, self.size_var, *SIZE_OPTIONS).grid(row=r, column=1, sticky="w")

        Label(param_frame, text="质量:").grid(row=r, column=2, sticky="e", padx=(12, 4))
        self.quality_var = StringVar(value=QUALITY_OPTIONS[0])
        OptionMenu(param_frame, self.quality_var, *QUALITY_OPTIONS).grid(row=r, column=3, sticky="w")

        r += 1
        Label(param_frame, text="数量:").grid(row=r, column=0, sticky="e", padx=(0, 4))
        self.count_var = IntVar(value=1)
        Spinbox(param_frame, from_=1, to=10, textvariable=self.count_var, width=5).grid(
            row=r, column=1, sticky="w"
        )

        Label(param_frame, text="推理模式:").grid(row=r, column=2, sticky="e", padx=(12, 4))
        self.thinking_var = StringVar(value=THINKING_OPTIONS[0])
        OptionMenu(param_frame, self.thinking_var, *THINKING_OPTIONS).grid(
            row=r, column=3, sticky="w"
        )

        r += 1
        Label(param_frame, text="背景:").grid(row=r, column=0, sticky="e", padx=(0, 4))
        self.bg_var = StringVar(value=BG_OPTIONS[0])
        OptionMenu(param_frame, self.bg_var, *BG_OPTIONS).grid(row=r, column=1, sticky="w")

        Label(param_frame, text="种子:").grid(row=r, column=2, sticky="e", padx=(12, 4))
        self.seed_var = StringVar()
        Entry(param_frame, textvariable=self.seed_var, width=12).grid(row=r, column=3, sticky="w")

        r += 1
        Label(param_frame, text="输出格式:").grid(row=r, column=0, sticky="e", padx=(0, 4))
        self.format_var = StringVar(value=FORMAT_OPTIONS[0])
        OptionMenu(param_frame, self.format_var, *FORMAT_OPTIONS).grid(
            row=r, column=1, sticky="w"
        )

        out_frame = LabelFrame(parent, text="输出设置")
        out_frame.pack(fill="x", **pad)

        r = 0
        Label(out_frame, text="保存到:").grid(row=r, column=0, sticky="e", padx=(0, 4))
        self.output_var = StringVar(value=str(OUTPUT_DIR.resolve()))
        Entry(out_frame, textvariable=self.output_var, width=40).grid(
            row=r, column=1, sticky="ew", padx=(0, 4)
        )
        Button(out_frame, text="浏览…", command=self._browse_output).grid(row=r, column=2)
        out_frame.columnconfigure(1, weight=1)

        r += 1
        Label(out_frame, text="文件名前缀:").grid(row=r, column=0, sticky="e", padx=(0, 4))
        self.prefix_var = StringVar(value="gpt-image")
        Entry(out_frame, textvariable=self.prefix_var, width=20).grid(row=r, column=1, sticky="w")

        btn_frame = Frame(parent)
        btn_frame.pack(fill="x", **pad)

        self.generate_btn = Button(
            btn_frame,
            text="🚀 生成图像",
            font=("Microsoft YaHei", 11, "bold"),
            bg="#4A90D9",
            fg="white",
            padx=20,
            pady=4,
            command=self._generate,
        )
        self.generate_btn.pack(side="left", padx=(0, 8))

        self.progress = ttk.Progressbar(btn_frame, mode="indeterminate", length=200)
        self.progress.pack(side="left", fill="x", expand=True)

    def _build_right_panel(self, parent):
        pad = {"padx": 8, "pady": 3}

        status_frame = LabelFrame(parent, text="运行日志")
        status_frame.pack(fill="both", expand=True, **pad)

        self.log_text = scrolledtext.ScrolledText(
            status_frame, height=10, wrap="word", state="disabled",
            font=("Consolas", 9),
        )
        self.log_text.pack(fill="both", expand=True)

        preview_frame = LabelFrame(parent, text="生成预览")
        preview_frame.pack(fill="both", expand=True, **pad)

        canvas = Canvas(preview_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(preview_frame, orient="vertical", command=canvas.yview)
        self.preview_container = ImagePreviewFrame(canvas)
        self.preview_container.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        canvas.create_window((0, 0), window=self.preview_container, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self._preview_canvas = canvas

        clear_btn = Button(parent, text="清空预览", command=self._clear_preview)
        clear_btn.pack(anchor="e", padx=8, pady=(0, 6))

    def _toggle_api_key_visibility(self):
        if self.api_key_entry.cget("show") == "*":
            self.api_key_entry.configure(show="")
            self._toggle_key_btn.configure(text="🙈")
        else:
            self.api_key_entry.configure(show="*")
            self._toggle_key_btn.configure(text="👁")

    def _browse_output(self):
        path = filedialog.askdirectory(initialdir=self.output_var.get())
        if path:
            self.output_var.set(path)

    def _clear_preview(self):
        self.preview_container.clear()
        self._generated_images.clear()

    def _log(self, msg: str):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _generate(self):
        api_key = self.api_key_var.get().strip() or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            messagebox.showerror("错误", "请在 API 配置中填写 API Key，或设置环境变量 OPENAI_API_KEY")
            return

        prompt = self.prompt_text.get("1.0", "end-1c").strip()
        if not prompt:
            messagebox.showerror("错误", "请输入提示词")
            return

        self.generate_btn.configure(state="disabled", text="⏳ 生成中…")
        self.progress.start(10)

        threading.Thread(target=self._do_generate, args=(api_key, prompt), daemon=True).start()

    def _do_generate(self, api_key: str, prompt: str):
        try:
            model = self.model_var.get()
            size = self.size_var.get()
            quality = self.quality_var.get()
            count = self.count_var.get()
            response_format = self.format_var.get()
            output_dir = Path(self.output_var.get())
            prefix = self.prefix_var.get().strip() or "gpt-image"

            client_kwargs = {"api_key": api_key}
            base_url = self.base_url_var.get().strip()
            if base_url:
                client_kwargs["base_url"] = base_url

            client = OpenAI(**client_kwargs)

            params = {
                "model": model,
                "prompt": prompt,
                "n": count,
                "size": size,
                "quality": quality,
                "response_format": response_format,
            }

            thinking = self.thinking_var.get()
            if thinking:
                params["thinking"] = thinking

            bg = self.bg_var.get()
            if bg:
                params["background"] = bg

            seed_raw = self.seed_var.get().strip()
            if seed_raw:
                params["seed"] = int(seed_raw)

            self.after(0, lambda: self._log(f"[请求] 模型={model}  尺寸={size}  质量={quality}  数量={count}"))
            if thinking:
                self.after(0, lambda: self._log(f"[请求] 推理模式={thinking}"))
            self.after(0, lambda: self._log(f"[提示] {prompt[:120]}{'…' if len(prompt) > 120 else ''}"))

            response = client.images.generate(**params)

            output_dir.mkdir(parents=True, exist_ok=True)
            saved_paths: list[Path] = []

            for i, image_data in enumerate(response.data):
                filename = f"{prefix}_{i+1:02d}.png"
                save_path = output_dir / filename

                if response_format == "b64_json":
                    _save_image_from_b64(image_data.b64_json, save_path)
                else:
                    _save_image_from_url(image_data.url, save_path)

                saved_paths.append(save_path)

            self.after(0, lambda: self._log(f"[完成] 成功生成 {len(saved_paths)} 张图像"))
            for p in saved_paths:
                self.after(0, lambda p=p: self._log(f"       {p}"))

            self.after(0, lambda: self._show_previews(saved_paths))

        except Exception as e:
            self.after(0, lambda: self._log(f"[错误] {e}"))
            self.after(0, lambda: messagebox.showerror("生成失败", str(e)))
        finally:
            self.after(0, self._finish_generate)

    def _show_previews(self, paths: list[Path]):
        for p in paths:
            try:
                self.preview_container.add_image(p)
            except Exception as e:
                self._log(f"[预览] 加载失败: {p.name} - {e}")
        self._preview_canvas.configure(scrollregion=self._preview_canvas.bbox("all"))
        self._generated_images.extend(paths)

    def _finish_generate(self):
        self.progress.stop()
        self.generate_btn.configure(state="normal", text="🚀 生成图像")


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
