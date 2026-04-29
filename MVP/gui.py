import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from dictionary_pipeline import DEFAULT_INPUT_DIR, DEFAULT_OUTPUT_DIR, list_html_files, process_corpus


class ParsingApp:
    def __init__(self, root: tk.Tk):
        self._root = root
        self._root.title("MVP: Парсинг словарных статей")

        self.style = ttk.Style()
        self.style.theme_use("clam")

        self._worker_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

        self._source_var = tk.StringVar(value=str(DEFAULT_INPUT_DIR))
        self._target_var = tk.StringVar(value=str(DEFAULT_OUTPUT_DIR))
        self._status_var = tk.StringVar(value="Готово к запуску")

        self._build_ui()
        self._validate_source()

    def _build_ui(self):
        frame = ttk.Frame(self._root, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)

        self._build_folder_row(frame, "Каталог статей:", self._source_var, 0)
        self._build_folder_row(frame, "Каталог результатов:", self._target_var, 1)

        self._progress = ttk.Progressbar(frame, mode="determinate")
        self._progress.grid(row=2, column=0, columnspan=3, sticky=tk.EW, pady=5)

        ttk.Label(frame, textvariable=self._status_var).grid(
            row=3, column=0, columnspan=3, sticky=tk.W, pady=(0, 5)
        )

        self._btn_start = ttk.Button(frame, text="Start", command=self._on_start)
        self._btn_start.grid(row=4, column=0, columnspan=3, pady=5)

        self._log_text = tk.Text(frame, height=14, state=tk.DISABLED, wrap=tk.WORD)
        self._log_text.grid(row=5, column=0, columnspan=3, sticky=tk.NSEW, pady=5)

        button_frame = ttk.Frame(frame)
        button_frame.grid(row=6, column=0, columnspan=3, sticky=tk.E)

        ttk.Button(button_frame, text="Очистить", command=self._on_clear).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="Сохранить лог", command=self._on_save).pack(side=tk.LEFT, padx=2)

        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(5, weight=1)

    def _build_folder_row(self, parent, label_text, variable, row):
        ttk.Label(parent, text=label_text).grid(row=row, column=0, sticky=tk.W)
        ttk.Entry(parent, textvariable=variable, state="readonly").grid(
            row=row, column=1, sticky=tk.EW, padx=5
        )
        ttk.Button(
            parent,
            text="Выбрать",
            command=lambda: self._choose_folder(variable),
        ).grid(row=row, column=2)

    def _choose_folder(self, variable: tk.StringVar):
        path = filedialog.askdirectory()
        if path:
            variable.set(path)
            self._validate_source()

    def _validate_source(self):
        source_path = Path(self._source_var.get())
        has_files = source_path.exists() and any(source_path.glob("**/*.html"))
        self._btn_start.config(state=tk.NORMAL if has_files else tk.DISABLED)

    def _on_start(self):
        if self._worker_thread and self._worker_thread.is_alive():
            self._on_stop()
            return

        source = Path(self._source_var.get())
        target = Path(self._target_var.get())

        if not source.exists():
            messagebox.showerror("Error", f"Source folder does not exist: {source}")
            return

        html_files = list_html_files(source)
        if not html_files:
            messagebox.showwarning("Warning", "Source folder is empty")
            return

        target.mkdir(parents=True, exist_ok=True)

        self._stop_event.clear()
        self._progress["maximum"] = len(html_files)
        self._progress["value"] = 0
        self._status_var.set("Запуск...")
        self._btn_start.config(text="Stop", command=self._on_stop)
        self._log(f"Старт: {len(html_files)} файлов")

        self._worker_thread = threading.Thread(
            target=self._run_pipeline,
            args=(source, target),
            daemon=True,
        )
        self._worker_thread.start()

    def _run_pipeline(self, source: Path, target: Path):
        def logger(message: str):
            self._root.after(0, self._log, message)

        def progress(current: int, total: int, relative_path: str):
            self._root.after(0, self._update_progress, current, total, relative_path)

        process_corpus(
            source_root=source,
            output_root=target,
            logger=logger,
            progress_callback=progress,
            stop_event=self._stop_event,
        )

        self._root.after(0, self._on_finished)

    def _update_progress(self, current: int, total: int, relative_path: str):
        self._progress["maximum"] = total
        self._progress["value"] = current
        self._status_var.set(f"{current}/{total}: {relative_path}")

    def _on_finished(self):
        self._btn_start.config(text="Start", command=self._on_start, state=tk.NORMAL)
        self._status_var.set("Готово")

    def _on_stop(self):
        self._stop_event.set()
        self._btn_start.config(text="Stopping...", state=tk.DISABLED)
        self._status_var.set("Остановка...")

    def _log(self, message: str):
        self._log_text.config(state=tk.NORMAL)
        self._log_text.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {message}\n")
        self._log_text.see(tk.END)
        self._log_text.config(state=tk.DISABLED)

    def _on_clear(self):
        self._log_text.config(state=tk.NORMAL)
        self._log_text.delete("1.0", tk.END)
        self._log_text.config(state=tk.DISABLED)

    def _on_save(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if path:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(self._log_text.get("1.0", tk.END))


def main():
    root = tk.Tk()
    root.geometry("900x600")
    app = ParsingApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
