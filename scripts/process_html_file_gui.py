from ulia_pav.gui import ParsingApp
from ProdamGarageXeX.split_articles import process_html_file
import tkinter as tk

if __name__ == "__main__":
    root = tk.Tk()
    root.tk.call('encoding', 'system', 'utf-8')
    # После добавления в process_html_file параметра print_fn эту функцию можно сразу передавать в GUI
    app = ParsingApp(root, process_html_file)
    root.mainloop()