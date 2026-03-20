import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json
import os
from pathlib import Path
import subprocess
import threading
import datetime

# Пример комментария:
# Если структура JSON изменится (в новой версии игры), вы можете добавить
# новые ключи поиска в классе RecipeParser в функциях _find_target_arrays
# и _extract_ingredient_from_node.
# Ключи поиска для массивов: "Ingredients", "Components", "RequiredItems".
# Ключи поиска для количества: "Amount", "Count", "Quantity", "amount".
# Ключи поиска для ID: "AllowedTypes", "CraftingIngredientTag", "Ingredient", "Item", "ID".

class DarkTheme:
    BG = "#1e1e1e"
    FG = "#cccccc"
    ENTRY_BG = "#2d2d2d"
    ENTRY_FG = "#cccccc"
    TREE_BG = "#252526"
    TREE_FG = "#cccccc"
    TREE_SEL = "#094771"
    HL = "#007acc"
    ERR = "#d32f2f"
    SUCCESS = "#388e3c"

class RecipeParser:
    def __init__(self, json_data):
        self.json_data = json_data
        self.ingredients = []
        self.recipe_name = "Неизвестно"
        self.item_id = "Неизвестно"
        self.imports = json_data.get("Imports", []) if isinstance(json_data, dict) else []
        self.parse()

    def _get_import_name(self, idx):
        try:
            val = int(idx)
            if val < 0:
                imp_idx = -val - 1
                if 0 <= imp_idx < len(self.imports):
                    name = self.imports[imp_idx].get("ObjectName", str(val))
                    if name and name.startswith("/Game/"):
                        name = name.split("/")[-1]
                    return name
            return str(val)
        except (ValueError, TypeError):
            return str(idx)

    def parse(self):
        self._find_basic_info(self.json_data)
        arrays = self._find_target_arrays(self.json_data)
        seen_ids = set()
        for arr in arrays:
            if id(arr) not in seen_ids:
                seen_ids.add(id(arr))
                self._process_ingredient_array(arr)

    def _find_basic_info(self, obj):
        if isinstance(obj, dict):
            if "CultureInvariantString" in obj and isinstance(obj["CultureInvariantString"], str) and obj["CultureInvariantString"]:
                if self.recipe_name == "Неизвестно" or len(self.recipe_name) > 30:
                    self.recipe_name = obj["CultureInvariantString"]
                    
            name_val = obj.get("Name")
            if name_val == "Caption":
                if obj.get("CultureInvariantString"):
                    self.recipe_name = str(obj["CultureInvariantString"])
                elif "Value" in obj and self.recipe_name == "Неизвестно":
                    self.recipe_name = str(obj["Value"])
            if name_val in ["Product", "PlaceableActorClass"] and "Value" in obj:
                val = obj["Value"]
                if isinstance(val, dict) and "AssetPath" in val:
                    ap = val["AssetPath"]
                    if isinstance(ap, dict) and "AssetName" in ap:
                        self.item_id = str(ap["AssetName"])
            
            # Поиск в стандартных JSON без UAsset структуры
            for k in ["RecipeName", "Name", "Title"]:
                if k in obj and isinstance(obj[k], str) and self.recipe_name == "Неизвестно":
                    self.recipe_name = obj[k]
                    
            for k, v in obj.items():
                if isinstance(v, (dict, list)):
                    self._find_basic_info(v)
        elif isinstance(obj, list):
            for item in obj:
                if isinstance(item, (dict, list)):
                    self._find_basic_info(item)

    def _find_target_arrays(self, obj, arrays=None):
        if arrays is None:
            arrays = []
        if isinstance(obj, dict):
            # Проверка стандартных ключей
            for k in ["Ingredients", "Components", "RequiredItems"]:
                if k in obj and isinstance(obj[k], list):
                    if obj[k] not in arrays:
                        arrays.append(obj[k])
                        
            # Проверка структуры UAssetAPI
            if obj.get("Name") in ["Ingredients", "Components", "RequiredItems", "CraftingObject"]:
                if "Value" in obj and isinstance(obj["Value"], list):
                    if obj["Value"] not in arrays:
                        arrays.append(obj["Value"])
                        
            for k, v in obj.items():
                if isinstance(v, (dict, list)):
                    self._find_target_arrays(v, arrays)
        elif isinstance(obj, list):
            for item in obj:
                if isinstance(item, (dict, list)):
                    self._find_target_arrays(item, arrays)
        return arrays

    def _process_ingredient_array(self, arr):
        for item in arr:
            if isinstance(item, dict):
                # Простейшая валидация, что это может быть ингредиент
                if item.get("StructType") == "CraftingIngredientSlot" or any(k in item for k in ["Ingredient", "Amount", "AllowedTypes", "amount", "Count", "Item"]):
                    self._extract_ingredient_from_node(item, arr)

    def _extract_ingredient_from_node(self, node, parent_list):
        item_id = "Unknown"
        amount = 0
        amount_ref = None
        amount_key = None
        is_uasset = False
        
        if node.get("StructType") == "CraftingIngredientSlot" and "Value" in node and isinstance(node["Value"], list):
            is_uasset = True
            for prop in node["Value"]:
                if isinstance(prop, dict):
                    p_name = prop.get("Name")
                    if p_name in ["AllowedTypes", "CraftingIngredientTag"]:
                        val = prop.get("Value")
                        if isinstance(val, list):
                            ids = []
                            for v in val:
                                if isinstance(v, dict) and "Value" in v:
                                   ids.append(str(v["Value"]))
                            item_id = ", ".join(ids) if ids else "Unknown"
                    elif p_name == "Amount":
                        val = prop.get("Value")
                        if isinstance(val, list) and len(val) > 0:
                            first_skill = val[0]
                            if isinstance(first_skill, dict) and "Value" in first_skill:
                                amount = first_skill["Value"]
                                amount_ref = prop
                                amount_key = "UASSET_AMOUNT"
                        elif isinstance(val, (int, float)):
                            amount = val
                            amount_ref = prop
                            amount_key = "Value"
        else:
            # Парсинг стандартного JSON формата
            for k in ["Ingredient", "Item", "Component", "ID", "AllowedTypes", "id", "name", "type"]:
                if k in node:
                    item_id = str(node[k])
                    break
                    
            for k in ["Amount", "Count", "Quantity", "amount", "count"]:
                if k in node:
                    amount = node[k]
                    amount_ref = node
                    amount_key = k
                    break
                    
        # Имя генерируется для удобства, если нет явного поля
        name = node.get("Name", f"Ингредиент {len(self.ingredients) + 1}")
        if is_uasset:
            if item_id and item_id != "Unknown":
                name = ", ".join([self._get_import_name(i.strip()) for i in item_id.split(",") if i.strip()])
            else:
                name = f"Слот ингредиента {len(self.ingredients) + 1}"
             
        self.ingredients.append({
            "name": str(name),
            "id": str(item_id),
            "amount": amount,
            "ref": amount_ref,
            "key": amount_key,
            "parent_list": parent_list,
            "node": node,
            "is_uasset": is_uasset
        })

    def update_ingredient_data(self, index, new_id, new_amount):
        if 0 <= index < len(self.ingredients):
            ing = self.ingredients[index]
            try:
                amt_val = int(new_amount)
            except ValueError:
                amt_val = 0
                
            ref = ing["ref"]
            key = ing["key"]
            if ref is not None and key is not None:
                if key == "UASSET_AMOUNT":
                    for skill_level in ref["Value"]:
                        if isinstance(skill_level, dict) and "Value" in skill_level:
                            skill_level["Value"] = amt_val
                else:
                    ref[key] = amt_val
            ing["amount"] = amt_val
            
            node = ing["node"]
            if ing["is_uasset"]:
                for prop in node.get("Value", []):
                    if isinstance(prop, dict) and prop.get("Name") in ["AllowedTypes", "CraftingIngredientTag"]:
                        val = prop.get("Value")
                        if isinstance(val, list) and len(val) > 0:
                            if "Value" in val[0]:
                                try:
                                    val[0]["Value"] = int(new_id)
                                except ValueError:
                                    val[0]["Value"] = new_id
            else:
                for k in ["Ingredient", "Item", "Component", "ID", "id"]:
                    if k in node:
                        try:
                            node[k] = int(new_id)
                        except ValueError:
                            node[k] = new_id
                        break
            ing["id"] = new_id

    def remove_ingredient(self, index):
        if 0 <= index < len(self.ingredients):
            ing = self.ingredients.pop(index)
            parent_list = ing["parent_list"]
            node = ing["node"]
            if parent_list is not None and node in parent_list:
                try:
                    parent_list.remove(node)
                except ValueError:
                    pass

    def update_all_amounts(self, new_amount=None, percent=None):
        for i in range(len(self.ingredients)):
            ing = self.ingredients[i]
            if new_amount is not None:
                amt_val = new_amount
            elif percent is not None:
                amt_val = max(1, int(round(ing["amount"] * percent)))
            else:
                continue
            self.update_ingredient_data(i, ing["id"], amt_val)

    def add_ingredient(self, template_index=0):
        if not self.ingredients:
            return False
        import copy
        template = self.ingredients[template_index]
        new_node = copy.deepcopy(template["node"])
        
        parent_list = template["parent_list"]
        if parent_list is not None:
            parent_list.append(new_node)
            self._extract_ingredient_from_node(new_node, parent_list)
            return True
        return False

def is_recipe_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read(50000)
            if any(k in content for k in ["Ingredients", "Components", "RequiredItems", "CraftingResult", "CraftingIngredientSlot", "CR_"]):
                return True
        return False
    except Exception:
         return False

class RecipeEditorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("SCUM Recipe Editor")
        self.root.geometry("1000x650")
        
        # Настройка иконки, если существует (icon.ico)
        icon_path = Path("icon.ico")
        if icon_path.exists():
            try:
                self.root.iconbitmap(icon_path)
            except tk.TclError:
                pass
        
        self.setup_styles()
        
        self.current_filepath = None
        self.parser = None
        self.unsaved_changes = False
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.build_ui()
        
    def setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        
        style.configure('.', background=DarkTheme.BG, foreground=DarkTheme.FG)
        style.configure('TFrame', background=DarkTheme.BG)
        style.configure('TLabel', background=DarkTheme.BG, foreground=DarkTheme.FG)
        style.configure('TButton', background=DarkTheme.ENTRY_BG, foreground=DarkTheme.FG, borderwidth=1)
        style.map('TButton', background=[('active', DarkTheme.TREE_SEL)])
        style.configure('TEntry', fieldbackground=DarkTheme.ENTRY_BG, foreground=DarkTheme.ENTRY_FG, insertcolor=DarkTheme.FG)
        
        style.configure('Treeview', background=DarkTheme.TREE_BG, foreground=DarkTheme.TREE_FG, fieldbackground=DarkTheme.TREE_BG, borderwidth=0)
        style.map('Treeview', background=[('selected', DarkTheme.TREE_SEL)], foreground=[('selected', DarkTheme.FG)])
        
        style.configure('Treeview.Heading', background=DarkTheme.ENTRY_BG, foreground=DarkTheme.FG, borderwidth=1)
        style.map('Treeview.Heading', background=[('active', DarkTheme.TREE_SEL)])
        
        # Настройка вкладок (Notebook)
        style.configure('TNotebook', background=DarkTheme.BG, borderwidth=0)
        style.configure('TNotebook.Tab', background=DarkTheme.ENTRY_BG, foreground=DarkTheme.FG, padding=[15, 5], font=("", 10))
        # Оранжевый цвет для выбранной вкладки и выделение при наведении
        style.map('TNotebook.Tab',
                  background=[('selected', '#e67e22'), ('active', '#4a4a4a')],
                  foreground=[('selected', '#ffffff')])
        
        # Стили для комбобокса (Пресеты %)
        style.configure('TCombobox', fieldforeground='black', foreground='black')
        style.map('TCombobox', 
                  fieldforeground=[('readonly', 'black')], 
                  foreground=[('readonly', 'black')])
        # Принудительно задаем черный текст для самого выпадающего списка
        self.root.option_add('*TCombobox*Listbox.foreground', 'black')
        self.root.option_add('*TCombobox*Listbox.background', 'white')
        
        style.configure('Red.TLabel', foreground=DarkTheme.ERR, font=("", 9, "bold"))
        
    def build_ui(self):
        # Создаем Notebook (вкладки)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Вкладка 1: Редактор
        self.tab_editor = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_editor, text="📝Editor")
        
        # Вкладка 2: Convert
        self.tab_convert = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_convert, text="⚙️Convert")
        
        self.build_editor_tab()
        self.build_convert_tab()

    def build_editor_tab(self):
        # Панель инструментов
        toolbar = ttk.Frame(self.tab_editor, padding=5)
        toolbar.pack(side=tk.TOP, fill=tk.X)
        
        ttk.Button(toolbar, text="Открыть директорию", command=self.open_directory).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="Сохранить", command=self.save_file).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="Обновить", command=self.reload_file).pack(side=tk.LEFT, padx=5)
        
        ttk.Label(toolbar, text="Поддержка только \"Рецептов\" из SCUM\\Content\\ConZ_Files\\Items\\Crafting\\Recipes\\Placeables", style="Red.TLabel").pack(side=tk.LEFT, padx=20)
        
        # Основная разбивка
        paned = ttk.PanedWindow(self.tab_editor, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Левая панель - список файлов
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=1)
        
        search_frame = ttk.Frame(left_frame)
        search_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(search_frame, text="Поиск:").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_var.trace("w", self.on_search)
        ttk.Entry(search_frame, textvariable=self.search_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Treeview для файлов
        self.tree_files = ttk.Treeview(left_frame, show="tree", selectmode="browse")
        self.tree_files.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        # Scrollbar файлов
        sc_files = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=self.tree_files.yview)
        sc_files.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree_files.configure(yscrollcommand=sc_files.set)
        
        self.tree_files.tag_configure("recipe", foreground=DarkTheme.FG)
        self.tree_files.tag_configure("non_recipe", foreground="#777777")
        self.tree_files.bind("<<TreeviewSelect>>", self.on_file_select)
        
        # Правая панель - рабочая область
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=3)
        
        # Инфо рецепта
        info_frame = ttk.Frame(right_frame)
        info_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(info_frame, text="Название рецепта:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.recipe_name_var = tk.StringVar()
        ent_rn = ttk.Entry(info_frame, textvariable=self.recipe_name_var, state="readonly", width=50)
        ent_rn.grid(row=0, column=1, sticky="w", padx=5, pady=2)
        
        ttk.Label(info_frame, text="ID предмета:").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        self.item_id_var = tk.StringVar()
        ent_id = ttk.Entry(info_frame, textvariable=self.item_id_var, state="readonly", width=50)
        ent_id.grid(row=1, column=1, sticky="w", padx=5, pady=2)
        
        preset_frame = ttk.LabelFrame(info_frame, text="Пресеты", padding=2)
        preset_frame.grid(row=0, column=2, rowspan=2, padx=20, sticky="ns")
        
        ttk.Button(preset_frame, text="1 ед.", width=5, command=self.preset_set_1).pack(side=tk.LEFT, padx=5, pady=2)
        
        self.preset_percent_var = tk.StringVar()
        self.preset_percent_var.set("% от текущего")
        percents = [f"{p}%" for p in range(90, 0, -10)]
        cb_percent = ttk.Combobox(preset_frame, textvariable=self.preset_percent_var, values=percents, width=15, state="readonly")
        cb_percent.pack(side=tk.LEFT, padx=5, pady=2)
        cb_percent.bind("<<ComboboxSelected>>", self.preset_apply_percent)
        
        self.preset_all_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(preset_frame, text="All", variable=self.preset_all_var).pack(side=tk.LEFT, padx=5, pady=2)
        
        # Редактор ингредиентов
        ttk.Label(right_frame, text="Ингредиенты (выберите для редактирования):", font=("", 10, "bold")).pack(anchor="w", pady=(10, 5))
        
        tree_frame = ttk.Frame(right_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        columns = ("name", "id", "amount")
        self.tree_ing = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        self.tree_ing.heading("name", text="Название ингредиента")
        self.tree_ing.heading("id", text="ID ингредиента (AllowedTypes)")
        self.tree_ing.heading("amount", text="Требуемое количество")
        
        self.tree_ing.column("name", width=200)
        self.tree_ing.column("id", width=300)
        self.tree_ing.column("amount", width=150, anchor="center")
        
        sc_ing = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree_ing.yview)
        sc_ing.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree_ing.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.tree_ing.configure(yscrollcommand=sc_ing.set)
        
        self.tree_ing.bind("<<TreeviewSelect>>", self.on_ing_select)
        
        # Панель редактирования ингредиентов
        edit_frame = ttk.Frame(right_frame, padding=10)
        edit_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(edit_frame, text="ID:").pack(side=tk.LEFT, padx=(0, 5))
        self.edit_id_var = tk.StringVar()
        ttk.Entry(edit_frame, textvariable=self.edit_id_var, width=30).pack(side=tk.LEFT, padx=(0, 15))
        
        ttk.Label(edit_frame, text="Кол-во:").pack(side=tk.LEFT, padx=(0, 5))
        self.edit_amount_var = tk.StringVar()
        vcmd = (self.root.register(self.validate_int), '%P')
        ttk.Entry(edit_frame, textvariable=self.edit_amount_var, width=10, validate='key', validatecommand=vcmd).pack(side=tk.LEFT, padx=(0, 15))
        
        ttk.Button(edit_frame, text="Применить", command=self.apply_ing_edit).pack(side=tk.LEFT, padx=5)
        ttk.Button(edit_frame, text="Добавить", command=self.add_ing).pack(side=tk.LEFT, padx=5)
        ttk.Button(edit_frame, text="Удалить", command=self.remove_ing).pack(side=tk.LEFT, padx=5)
        
        # Статус бар
        self.status_var = tk.StringVar()
        self.status_var.set("Готов")
        self.status_bar = ttk.Label(self.tab_editor, textvariable=self.status_var, background=DarkTheme.ENTRY_BG, padding=3)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.json_file_mapping = {}
        self.all_files_items = []
        
    def validate_int(self, P):
        if P == "" or P.isdigit():
            return True
        return False

    def open_directory(self):
        if self.unsaved_changes:
            if not messagebox.askyesno("Сохранение", "У вас есть несохраненные изменения. Сбросить их и открыть новую папку?"):
                return
                
        directory = filedialog.askdirectory(title="Выберите папку с JSON")
        if not directory: return
        
        self.tree_files.delete(*self.tree_files.get_children())
        self.json_file_mapping.clear()
        self.all_files_items.clear()
        
        self.set_status("Сканирование директории...")
        self.root.update()
        
        recipes_count = 0
        dir_path = Path(directory)
        for root_dir, _, files in os.walk(directory):
            for f in files:
                if f.endswith(".json"):
                    f_path = Path(root_dir) / f
                    rel_path = f_path.relative_to(dir_path)
                    
                    is_rec = is_recipe_file(f_path)
                    color = "recipe" if is_rec else "non_recipe"
                    if is_rec:
                        recipes_count += 1
                    
                    iid = self.tree_files.insert("", "end", text=str(rel_path), tags=(color,))
                    self.json_file_mapping[iid] = f_path
                    self.all_files_items.append((rel_path, iid))
                    
        self.set_status(f"Найдено {len(self.all_files_items)} JSON файлов. Из них рецептов: {recipes_count}")
        self.unsaved_changes = False
        self.clear_workspace()

    def on_search(self, *args):
        query = self.search_var.get().lower()
        # Быстрая фильтрация UI элементов дерева
        for iid in self.tree_files.get_children():
            self.tree_files.detach(iid)
        
        for rel_path, iid in self.all_files_items:
            if query in str(rel_path).lower() or query == "":
                self.tree_files.reattach(iid, "", "end")

    def on_file_select(self, event):
        selection = self.tree_files.selection()
        if not selection: return
        
        iid = selection[0]
        filepath = self.json_file_mapping.get(iid)
        if not filepath: return
        
        if self.current_filepath == filepath:
            return
            
        if self.unsaved_changes:
            if not messagebox.askyesno("Сохранение", "У вас есть несохраненные изменения. Сбросить их и загрузить новый файл?"):
                # Возврат выделения назад сложно реализуем просто в Tkinter без флажков,
                # оставляем сброс
                pass
            else:
                 self.load_file(filepath)
            return

        self.load_file(filepath)

    def load_file(self, filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            self.set_status(f"Ошибка загрузки: {e}", error=True)
            messagebox.showerror("Ошибка парсинга", f"Файл поврежден или не является валидным JSON:\n{e}")
            return
            
        self.parser = RecipeParser(data)
        self.current_filepath = filepath
        self.unsaved_changes = False
        
        self.refresh_workspace()
        self.set_status(f"Загружен: {filepath.name}")

    def save_file(self):
        if not self.parser or not self.current_filepath: return
        
        try:
            with open(self.current_filepath, 'w', encoding='utf-8') as f:
                json.dump(self.parser.json_data, f, indent=4, ensure_ascii=False)
            self.unsaved_changes = False
            self.set_status("Файл успешно сохранен", success=True)
        except Exception as e:
            self.set_status(f"Ошибка сохранения: {e}", error=True)
            messagebox.showerror("Ошибка", f"Не удалось сохранить:\n{e}")

    def reload_file(self):
        if not self.current_filepath: return
        if self.unsaved_changes:
            if not messagebox.askyesno("Внимание", "Все несохраненные изменения будут потеряны. Продолжить?"):
                return
        self.unsaved_changes = False
        self.load_file(self.current_filepath)

    def clear_workspace(self):
        self.recipe_name_var.set("")
        self.item_id_var.set("")
        self.tree_ing.delete(*self.tree_ing.get_children())
        self.edit_id_var.set("")
        self.edit_amount_var.set("")
        self.current_filepath = None
        self.parser = None

    def refresh_workspace(self):
        if not self.parser: return
        
        self.recipe_name_var.set(self.parser.recipe_name)
        self.item_id_var.set(self.parser.item_id)
        
        self.tree_ing.delete(*self.tree_ing.get_children())
        
        for i, ing in enumerate(self.parser.ingredients):
            self.tree_ing.insert("", "end", iid=str(i), values=(ing["name"], ing["id"], ing["amount"]))
            
        self.edit_id_var.set("")
        self.edit_amount_var.set("")

    def on_ing_select(self, event):
        selection = self.tree_ing.selection()
        if not selection: return
        idx = int(selection[0])
        ing = self.parser.ingredients[idx]
        
        self.edit_id_var.set(str(ing["id"]))
        self.edit_amount_var.set(str(ing["amount"]))

    def apply_ing_edit(self):
        if not self.parser: return
        selection = self.tree_ing.selection()
        if not selection: return
        idx = int(selection[0])
        
        new_id = self.edit_id_var.get()
        new_amount = self.edit_amount_var.get()
        if not new_amount.isdigit():
            messagebox.showwarning("Внимание", "Количество должно быть положительным целым числом.")
            return
            
        self.parser.update_ingredient_data(idx, new_id, new_amount)
        self.unsaved_changes = True
        self.set_status(f"Изменено (Несохранено): Ингредиент {idx+1}")
        
        # Обновляем отображение в дереве
        ing = self.parser.ingredients[idx]
        self.tree_ing.item(str(idx), values=(ing["name"], ing["id"], ing["amount"]))

    def add_ing(self):
        if not self.parser: return
        selection = self.tree_ing.selection()
        template_idx = int(selection[0]) if selection else 0
        
        if self.parser.add_ingredient(template_idx):
            self.unsaved_changes = True
            self.refresh_workspace()
            self.set_status("Добавлен новый ингредиент (Несохранено)")
        else:
            messagebox.showinfo("Инфо", "Не удалось скопировать структуру для нового ингредиента.")

    def remove_ing(self):
        if not self.parser: return
        selection = self.tree_ing.selection()
        if not selection: return
        idx = int(selection[0])
        
        if messagebox.askyesno("Удаление", f"Удалить этот ингредиент?"):
            self.parser.remove_ingredient(idx)
            self.unsaved_changes = True
            self.refresh_workspace()
            self.set_status("Ингредиент удален (Несохранено)")

    def set_status(self, msg, error=False, success=False):
        self.status_var.set(msg)
        if error:
            self.status_bar.configure(foreground=DarkTheme.ERR)
        elif success:
            self.status_bar.configure(foreground=DarkTheme.SUCCESS)
        else:
            self.status_bar.configure(foreground=DarkTheme.FG)

    def build_convert_tab(self):
        main_frame = ttk.Frame(self.tab_convert, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Настройки
        settings_frame = ttk.LabelFrame(main_frame, text="Настройки конвертации", padding=10)
        settings_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(settings_frame, text="Директория (json_exports / uassets):").grid(row=0, column=0, sticky="w", pady=5)
        self.convert_dir_var = tk.StringVar()
        ttk.Entry(settings_frame, textvariable=self.convert_dir_var, width=60).grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(settings_frame, text="Обзор", command=self.browse_convert_dir).grid(row=0, column=2, padx=5, pady=5)
        
        ttk.Label(settings_frame, text="Путь к UAssetGUI.exe:").grid(row=1, column=0, sticky="w", pady=5)
        self.uassetgui_path_var = tk.StringVar()
        
        # Ищем UAssetGUI рядом или оставляем пустым
        import sys
        base_dir = Path(sys.argv[0]).parent.absolute()
        local_uassetgui = base_dir / "UAssetGUI.exe"
        
        if local_uassetgui.exists():
            uasset_default = str(local_uassetgui)
        else:
            uasset_default = r"C:\Workspace\Tools\UAssetGUI\UAssetGUI.exe"
            if not os.path.exists(uasset_default):
                 uasset_default = ""
        self.uassetgui_path_var.set(uasset_default)
        
        ttk.Entry(settings_frame, textvariable=self.uassetgui_path_var, width=60).grid(row=1, column=1, padx=5, pady=5)
        ttk.Button(settings_frame, text="Обзор", command=self.browse_uassetgui).grid(row=1, column=2, padx=5, pady=5)
        
        ttk.Label(settings_frame, text="Версия движка:").grid(row=2, column=0, sticky="w", pady=5)
        self.engine_version_var = tk.StringVar(value="VER_UE4_27")
        ttk.Entry(settings_frame, textvariable=self.engine_version_var, width=20).grid(row=2, column=1, sticky="w", padx=5, pady=5)
        
        # Действия
        actions_frame = ttk.LabelFrame(main_frame, text="Действия", padding=10)
        actions_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(actions_frame, text="Конвертировать в JSON (to_json)", command=self.start_convert_to_json, width=35).pack(side=tk.LEFT, padx=10, pady=5)
        ttk.Button(actions_frame, text="Конвертировать в UAsset (to_uasset)", command=self.start_convert_to_uasset, width=35).pack(side=tk.LEFT, padx=10, pady=5)
        
        # Логи
        log_frame = ttk.LabelFrame(main_frame, text="Логи", padding=10)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.convert_log_text = tk.Text(log_frame, state="disabled", background=DarkTheme.ENTRY_BG, foreground=DarkTheme.FG, height=15)
        self.convert_log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        sc_log = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.convert_log_text.yview)
        sc_log.pack(side=tk.RIGHT, fill=tk.Y)
        self.convert_log_text.configure(yscrollcommand=sc_log.set)
        
    def log_convert(self, msg):
        self.convert_log_text.configure(state="normal")
        self.convert_log_text.insert(tk.END, msg + "\n")
        self.convert_log_text.see(tk.END)
        self.convert_log_text.configure(state="disabled")
        
    def browse_convert_dir(self):
        d = filedialog.askdirectory(title="Выберите папку с файлами")
        if d:
            self.convert_dir_var.set(d)
            
    def browse_uassetgui(self):
        f = filedialog.askopenfilename(title="Укажите путь к UAssetGUI.exe", filetypes=[("Executable", "*.exe")])
        if f:
            self.uassetgui_path_var.set(f)

    def start_convert_to_json(self):
        directory = self.convert_dir_var.get()
        uassetgui = self.uassetgui_path_var.get()
        engine = self.engine_version_var.get()
        
        if not directory or not os.path.exists(directory):
            messagebox.showerror("Ошибка", "Директория не выбрана или не существует!")
            return
        if not uassetgui or not os.path.exists(uassetgui):
            messagebox.showerror("Ошибка", "UAssetGUI.exe не найден!")
            return
            
        files = [Path(root) / f for root, _, files in os.walk(directory) for f in files if f.lower().endswith('.uasset')]
        if not files:
            messagebox.showinfo("Инфо", "UAsset файлы не найдены в указанной директории.")
            return
            
        import sys
        base_dir = Path(sys.argv[0]).parent.absolute()
        timestamp = datetime.datetime.now().strftime("%d_%m_%y_%H%M")
        log_file = base_dir / f"to_json_{timestamp}.log"
        self.log_convert(f"Найдено {len(files)} UAsset файлов. Запускаем конвертацию to_json...")
        threading.Thread(target=self.run_conversion_batch, args=(files, "tojson", uassetgui, engine, directory, log_file), daemon=True).start()

    def start_convert_to_uasset(self):
        directory = self.convert_dir_var.get()
        uassetgui = self.uassetgui_path_var.get()
        engine = self.engine_version_var.get()
        
        if not directory or not os.path.exists(directory):
            messagebox.showerror("Ошибка", "Директория не выбрана или не существует!")
            return
        if not uassetgui or not os.path.exists(uassetgui):
            messagebox.showerror("Ошибка", "UAssetGUI.exe не найден!")
            return
            
        files = [Path(root) / f for root, _, files in os.walk(directory) for f in files if f.lower().endswith('.json')]
        if not files:
            messagebox.showinfo("Инфо", "JSON файлы не найдены в указанной директории.")
            return
            
        import sys
        base_dir = Path(sys.argv[0]).parent.absolute()
        timestamp = datetime.datetime.now().strftime("%d_%m_%y_%H%M")
        log_file = base_dir / f"to_uasset_{timestamp}.log"
        self.log_convert(f"Найдено {len(files)} JSON файлов. Запускаем конвертацию to_uasset...")
        threading.Thread(target=self.run_conversion_batch, args=(files, "fromjson", uassetgui, engine, directory, log_file), daemon=True).start()

    def run_conversion_batch(self, files, mode, uassetgui_path, engine_version, main_folder, log_file=None):
        total = len(files)
        success_count = 0
        base_folder = Path(main_folder)
        
        def write_log(text):
            if log_file:
                try:
                    with open(log_file, "a", encoding="utf-8") as lf:
                        lf.write(text + "\n")
                except:
                    pass
                    
        write_log(f"=== Начало конвертации ({mode}) ===")
        write_log(f"Всего файлов: {total}")
        
        for i, fpath in enumerate(files):
            try:
                if mode == "tojson":
                    json_exports_folder = base_folder / "json_exports"
                    try:
                        rel = fpath.relative_to(base_folder)
                        out_sub = json_exports_folder / rel.parent
                        out_sub.mkdir(parents=True, exist_ok=True)
                        out_path = out_sub / fpath.with_suffix('.json').name
                    except ValueError:
                        json_exports_folder.mkdir(parents=True, exist_ok=True)
                        out_path = json_exports_folder / fpath.with_suffix('.json').name
                    cmd = [uassetgui_path, "tojson", str(fpath), str(out_path), engine_version]
                else:
                    final_uassets_folder = base_folder / "final_uassets"
                    try:
                        rel_base = base_folder
                        if fpath.parent.name in ["json_exports", "edited_json"]:
                            rel_base = fpath.parent
                        elif "json_exports" in fpath.parts:
                            idx = fpath.parts.index("json_exports")
                            rel_base = Path(*fpath.parts[:idx+1])
                            
                        rel = fpath.relative_to(rel_base)
                        out_sub = final_uassets_folder / rel.parent
                        out_sub.mkdir(parents=True, exist_ok=True)
                        out_path = out_sub / fpath.with_suffix('.uasset').name
                    except ValueError:
                        final_uassets_folder.mkdir(parents=True, exist_ok=True)
                        out_path = final_uassets_folder / fpath.with_suffix('.uasset').name
                    cmd = [uassetgui_path, "fromjson", str(fpath), str(out_path), engine_version]
                
                startupinfo = None
                creation_flags = 0
                if os.name == 'nt':
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    startupinfo.wShowWindow = subprocess.SW_HIDE
                    creation_flags = subprocess.CREATE_NO_WINDOW
                    
                self.root.after(0, lambda p=fpath.name: self.log_convert(f"[{i+1}/{total}] Конвертация {p}..."))
                write_log(f"[{i+1}/{total}] Конвертация: {fpath.name}")
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, cwd=str(fpath.parent), startupinfo=startupinfo, creationflags=creation_flags)
                
                if out_path.exists() and out_path.stat().st_size > 0:
                    success_count += 1
                    write_log(f"  УСПЕХ -> {out_path}")
                else:
                    err = result.stderr or result.stdout or "Unknown Error"
                    self.root.after(0, lambda p=fpath.name, e=err: self.log_convert(f"Ошибка {p}: {e[:150]}"))
                    write_log(f"  ОШИБКА -> {err}")
            except Exception as e:
                self.root.after(0, lambda p=fpath.name, e=str(e): self.log_convert(f"Исключение {p}: {e}"))
                write_log(f"  ИСКЛЮЧЕНИЕ -> {e}")
                
        self.root.after(0, lambda s=success_count, t=total: self.log_convert(f"✅ Готово! Успешно: {s}/{t}\n"))
        write_log(f"=== Завершено. Успешно: {success_count} из {total} ===")
        self.root.after(0, lambda s=success_count, t=total: messagebox.showinfo("Конвертация", f"Завершено!\nУспешно: {s} из {t}"))

    def on_closing(self):
        if self.unsaved_changes:
            ans = messagebox.askyesnocancel("Выход", "У вас есть несохраненные изменения. Сохранить перед выходом?")
            if ans is True:
                self.save_file()
                self.root.destroy()
            elif ans is False:
                self.root.destroy()
            # Отмена - ничего не делаем
        else:
            self.root.destroy()

    def preset_set_1(self):
        if self.preset_all_var.get():
            if messagebox.askyesno("Подтверждение", "Установить количество 1 для ВСЕХ рецептов в загруженной папке?"):
                self.apply_to_all_recipes(new_amount=1)
        else:
            if not self.parser: return
            self.parser.update_all_amounts(new_amount=1)
            self.unsaved_changes = True
            self.refresh_workspace()
            self.set_status("Установлено 1 ед. для текущего макета (Несохранено)")

    def preset_apply_percent(self, event):
        val = self.preset_percent_var.get()
        if not val.endswith("%"): return
        
        self.root.focus_set()
        try:
            percent = int(val[:-1]) / 100.0
        except ValueError:
            return
            
        if self.preset_all_var.get():
            if messagebox.askyesno("Подтверждение", f"Изменить количество до {val} для ВСЕХ рецептов в папке?"):
                self.apply_to_all_recipes(percent=percent)
        else:
            if not self.parser: return
            self.parser.update_all_amounts(percent=percent)
            self.unsaved_changes = True
            self.refresh_workspace()
            self.set_status(f"Количество изменено до {val} (Несохранено)")
        
        self.preset_percent_var.set("% от текущего")

    def apply_to_all_recipes(self, new_amount=None, percent=None):
        count = 0
        for iid, f_path in self.json_file_mapping.items():
            if "recipe" in self.tree_files.item(iid, "tags"):
                try:
                    with open(f_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    parser = RecipeParser(data)
                    parser.update_all_amounts(new_amount=new_amount, percent=percent)
                    with open(f_path, 'w', encoding='utf-8') as f:
                        json.dump(parser.json_data, f, indent=4, ensure_ascii=False)
                    count += 1
                except Exception as e:
                    print(f"Ошибка с файлом {f_path}: {e}")
                    
        if self.current_filepath:
            self.unsaved_changes = False
            self.load_file(self.current_filepath)
            
        self.set_status(f"Пресет применен и сохранен для {count} файлов.", success=True)
        messagebox.showinfo("Готово", f"Пресет успешно применен и сохранен для {count} рецептов.")

if __name__ == "__main__":
    root = tk.Tk()
    app = RecipeEditorApp(root)
    root.mainloop()
