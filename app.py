import os
import sys
import threading
import json
import pandas as pd
from datetime import datetime
import webview

# 导入匹配核心逻辑
from matcher import CopywritingMatcher

class Api:
    def __init__(self):
        self._window = None
        self.matcher = None

    def load_settings(self):
        """
        加载用户界面设置，包括皮肤、模糊度、透明度、自定义背景
        """
        settings_path = os.path.join(os.getcwd(), "app_settings.json")
        settings = {}
        if os.path.exists(settings_path):
            try:
                with open(settings_path, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
            except Exception as e:
                print(f"Error loading settings: {e}")
        
        # 尝试读取自定义背景图片
        bg_path = os.path.join(os.getcwd(), "custom_background.dat")
        if os.path.exists(bg_path):
            try:
                with open(bg_path, 'r', encoding='utf-8') as f:
                    settings['bgImage'] = f.read()
            except Exception as e:
                print(f"Error loading custom background: {e}")
        
        return settings

    def save_settings(self, settings_json):
        """
        保存用户界面设置
        """
        try:
            settings = json.loads(settings_json)
            
            # 分离背景图片单独保存，避免 json 文件过大
            bg_image = settings.pop('bgImage', None)
            bg_path = os.path.join(os.getcwd(), "custom_background.dat")
            
            if bg_image and bg_image.startswith("data:"):
                with open(bg_path, 'w', encoding='utf-8') as f:
                    f.write(bg_image)
            else:
                # 如果背景图为空或非 base64 数据，删除自定义背景文件
                if os.path.exists(bg_path):
                    try:
                        os.remove(bg_path)
                    except Exception:
                        pass

            settings_path = os.path.join(os.getcwd(), "app_settings.json")
            with open(settings_path, 'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=False, indent=4)
            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def select_file(self, file_type):
        """
        打开原生的保存/选择文件对话框
        file_type: 'inventory' (库存) 或 'input' (待处理输入)
        """
        file_types = ('Excel 或者是 CSV (*.xlsx;*.xls;*.csv)', 'Excel 表格 (*.xlsx;*.xls)', 'CSV 文件 (*.csv)', '所有文件 (*.*)')
        if file_type == 'inventory':
            result = self._window.create_file_dialog(
                webview.OPEN_DIALOG, 
                file_types=file_types
            )
            if result:
                return result[0]
        elif file_type == 'input':
            result = self._window.create_file_dialog(
                webview.OPEN_DIALOG, 
                file_types=file_types
            )
            if result:
                return result[0]
        return ""

    def get_default_inventory_path(self):
        """
        获取默认的库存文件绝对路径
        """
        return os.path.join(os.getcwd(), "文案库存.xlsx").replace('\\', '/')

    def get_columns(self, file_path):
        """
        读取选中文案表格的表头列名
        """
        if not file_path or not os.path.exists(file_path):
            return []
        try:
            if file_path.endswith('.csv'):
                try:
                    df = pd.read_csv(file_path, nrows=2, encoding='utf-8')
                except UnicodeDecodeError:
                    df = pd.read_csv(file_path, nrows=2, encoding='gbk')
            else:
                df = pd.read_excel(file_path, nrows=2)
            return list(df.columns)
        except Exception as e:
            return {"error": str(e)}

    def run_processing(self, inv_path, input_path, col_name, prefix, threshold, mode):
        """
        异步运行文本相似度查重算法
        """
        threading.Thread(
            target=self._run_processing_worker,
            args=(inv_path, input_path, col_name, prefix, threshold, mode),
            daemon=True
        ).start()
        return {"status": "started"}

    def _run_processing_worker(self, inv_path, input_path, col_name, prefix, threshold, mode):
        try:
            # 1. 初始化匹配算法引擎
            self.report_progress(0.05, "正在初始化匹配算法和库存...")
            self.matcher = CopywritingMatcher(inv_path, id_prefix=prefix, threshold=float(threshold), mode=mode)

            # 2. 读取文案输入表格
            self.report_progress(0.1, "正在载入需要比对的新文案...")
            if input_path.endswith('.csv'):
                try:
                    df_input = pd.read_csv(input_path, encoding='utf-8')
                except UnicodeDecodeError:
                    df_input = pd.read_csv(input_path, encoding='gbk')
            else:
                df_input = pd.read_excel(input_path)

            target_col = None
            if col_name in df_input.columns:
                target_col = col_name
            elif len(df_input.columns) > 0:
                target_col = df_input.columns[0]
            
            if target_col is None:
                raise ValueError("未能在输入文件中找到可用的文案内容列！")

            new_texts = df_input[target_col].tolist()
            total_count = len(new_texts)
            
            # 发送行数统计
            self._window.evaluate_js(f"window.updateTotalCount({total_count});")
            
            if total_count == 0:
                raise ValueError("导入的文案表格为空，没有可处理的记录！")

            # 3. 运行匹配
            def progress_cb(cur, tot, msg):
                p = 0.15 + (cur / tot) * 0.70
                self.report_progress(p, msg)

            results = self.matcher.process_batch(df_input, target_col, progress_callback=progress_cb)

            # 4. 导出结果至原目录
            self.report_progress(0.88, "正在写入并保存结果表格...")
            df_output = df_input.copy()
            df_output['分配编号'] = [r['分配编号'] for r in results]
            df_output['匹配状态'] = [r['匹配状态'] for r in results]
            df_output['相似度'] = [r['相似度'] for r in results]
            df_output['最相似文案'] = [r['最相似文案'] for r in results]

            input_dir, input_name = os.path.split(input_path)
            name_part, ext_part = os.path.splitext(input_name)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_filename = f"{name_part}_比对结果_{timestamp}.xlsx"
            out_path = os.path.join(input_dir, out_filename)

            self.report_progress(0.92, "正在写入表格磁盘文件...")
            df_output.to_excel(out_path, index=False)

            self.report_progress(0.98, "正在更新界面预览数据...")
            matched_count = sum(1 for r in results if "已存在" in r['匹配状态'])
            new_count = sum(1 for r in results if r['匹配状态'] == "新文案")

            # 传递前 200 条用于前端表格展示
            preview_results = results[:200]
            results_json = json.dumps(preview_results, ensure_ascii=False)
            escaped_json = results_json.replace('\\', '\\\\').replace("'", "\\'").replace('"', '\\"')
            
            # 通知前端渲染
            js_cmd = f"window.showResults('{escaped_json}', {matched_count}, {new_count}, '{out_path.replace(chr(92), '/')}');"
            self._window.evaluate_js(js_cmd)

        except Exception as e:
            err_str = str(e).replace('\\', '\\\\').replace("'", "\\'").replace('"', '\\"')
            self._window.evaluate_js(f"window.showError('{err_str}');")

    def report_progress(self, progress, msg):
        self._window.evaluate_js(f"window.updateProgress({progress}, '{msg}');")
        
    def open_folder(self, file_path):
        """
        打开文件输出文件夹
        """
        if not file_path:
            return
        folder = os.path.dirname(file_path)
        if os.path.exists(folder):
            os.startfile(folder)

def get_resource_path(relative_path):
    """ 获取资源的绝对路径，兼容开发环境与 PyInstaller 打包环境 """
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包后的临时解压目录
        base_path = sys._MEIPASS
    else:
        # 开发环境下，使用当前脚本所在的目录
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

if __name__ == "__main__":
    api = Api()
    
    # 获取前端 HTML 路径，通过 get_resource_path 兼容打包环境
    html_path = get_resource_path(os.path.join('web', 'index.html'))
    
    # 启动桌面端 WebView2 独立应用窗口
    window = webview.create_window(
        '爆贴文案查重与库存管理系统', 
        html_path, 
        js_api=api, 
        width=1160, 
        height=780,
        min_size=(1050, 720),
        text_select=True
    )
    api._window = window
    
    # 运行事件循环，并加载独立的客户端图标（.ico）
    icon_path = get_resource_path('app_icon.ico')
    if os.path.exists(icon_path):
        webview.start(icon=icon_path)
    else:
        webview.start()

