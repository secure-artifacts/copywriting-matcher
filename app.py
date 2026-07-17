import os
import sys
import threading
import json
import pandas as pd
from datetime import datetime
import webview
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

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

    def select_credentials_file(self):
        """
        打开原生文件选择对话框选择谷歌服务账号 JSON 凭证文件
        """
        file_types = ('JSON Credentials (*.json)', '所有文件 (*.*)')
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

    def get_google_columns(self, url, credentials_path, sheet_name=None):
        """
        读取谷歌表格的列名
        """
        if not url or not credentials_path:
            return []
        try:
            from google.oauth2.service_account import Credentials
            import gspread
            
            scopes = [
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive'
            ]
            credentials = Credentials.from_service_account_file(credentials_path, scopes=scopes)
            self.gc = gspread.authorize(credentials)
            self.sh = self.gc.open_by_url(url)
            
            if sheet_name:
                worksheet = self.sh.worksheet(sheet_name)
            else:
                worksheet = self.sh.get_worksheet(0)
                
            headers = worksheet.row_values(1)
            return headers
        except Exception as e:
            return {"error": str(e)}

    def get_google_worksheets(self, url, credentials_path):
        """
        验证谷歌表格连接并获取所有子工作表名称
        """
        if not url or not credentials_path:
            return []
        try:
            from google.oauth2.service_account import Credentials
            import gspread
            
            scopes = [
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive'
            ]
            credentials = Credentials.from_service_account_file(credentials_path, scopes=scopes)
            gc = gspread.authorize(credentials)
            sh = gc.open_by_url(url)
            return [ws.title for ws in sh.worksheets()]
        except Exception as e:
            return {"error": str(e)}

    def run_processing(self, inv_path, input_path, col_name, write_col_name, prefix, threshold, mode,
                       use_google_sheets=False, google_sheets_url="", google_sheet_name="", google_creds_path="",
                       use_google_input=False, google_input_url="", google_input_name="",
                       ai_classify_enable=False, ai_api_key="", ai_model="gemini-3.1-flash-lite",
                       ai_batch_size=100, ai_concurrency=3, ai_col_name="AI分类", ai_rules="",
                       translate_mode="none", translate_api_key="", translate_platform="google-ai-studio",
                       translate_model="gemini-3.1-flash-lite", translate_proxy=""):
        """
        异步运行文本相似度查重算法
        """
        threading.Thread(
            target=self._run_processing_worker,
            args=(inv_path, input_path, col_name, write_col_name, prefix, threshold, mode,
                  use_google_sheets, google_sheets_url, google_sheet_name, google_creds_path,
                  use_google_input, google_input_url, google_input_name,
                  ai_classify_enable, ai_api_key, ai_model, ai_batch_size, ai_concurrency, ai_col_name, ai_rules,
                  translate_mode, translate_api_key, translate_platform, translate_model, translate_proxy),
            daemon=True
        ).start()
        return {"status": "started"}

    def _run_processing_worker(self, inv_path, input_path, col_name, write_col_name, prefix, threshold, mode,
                               use_google_sheets=False, google_sheets_url="", google_sheet_name="", google_creds_path="",
                               use_google_input=False, google_input_url="", google_input_name="",
                               ai_classify_enable=False, ai_api_key="", ai_model="gemini-3.1-flash-lite",
                               ai_batch_size=100, ai_concurrency=3, ai_col_name="AI分类", ai_rules="",
                               translate_mode="none", translate_api_key="", translate_platform="google-ai-studio",
                               translate_model="gemini-3.1-flash-lite", translate_proxy=""):
        try:
            # 1. 初始化匹配算法引擎
            self.report_progress(0.05, "正在初始化匹配算法和库存...")
            
            # 如果是语义模式，先检测依赖是否可用，不可用时安全降级
            actual_mode = mode
            if mode == "semantic":
                try:
                    import sentence_transformers  # noqa: F401
                except ImportError:
                    actual_mode = "tfidf"
                    self.log_message('warning', '[匹配] 未检测到 sentence-transformers 依赖，已自动降级为 TF-IDF 字面查重模式。')
                    self._window.evaluate_js("window.updateProgress(0.05, '⚠️ 未找到语义模型依赖，已切换为 TF-IDF 字面查重模式');")
            
            self.matcher = CopywritingMatcher(
                inv_path, 
                id_prefix=prefix, 
                threshold=float(threshold), 
                mode=actual_mode,
                use_google_sheets=use_google_sheets,
                google_sheets_url=google_sheets_url,
                google_sheet_name=google_sheet_name,
                google_creds_path=google_creds_path
            )


            # 2. 读取文案输入表格
            self.report_progress(0.1, "正在载入需要比对的新文案...")
            if use_google_input:
                from google.oauth2.service_account import Credentials
                import gspread
                
                scopes = [
                    'https://www.googleapis.com/auth/spreadsheets',
                    'https://www.googleapis.com/auth/drive'
                ]
                credentials = Credentials.from_service_account_file(google_creds_path, scopes=scopes)
                gc = gspread.authorize(credentials)
                sh = gc.open_by_url(google_input_url)
                
                if google_input_name:
                    worksheet_input = sh.worksheet(google_input_name)
                else:
                    worksheet_input = sh.get_worksheet(0)
                    
                data = worksheet_input.get_all_values()
                if not data or len(data) == 0:
                    raise ValueError("谷歌待比对工作表为空，没有可读取的记录！")
                    
                headers = data[0]
                rows = data[1:]
                df_input = pd.DataFrame(rows, columns=headers)
            else:
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

            # 3. 运行匹配 (直接使用原始外语列进行比对)
            def progress_cb(cur, tot, msg):
                p = 0.15 + (cur / max(tot, 1)) * 0.40
                self.report_progress(p, msg)

            results = self.matcher.process_batch(df_input, target_col, progress_callback=progress_cb)

            # 相似度比对完成，通知进度
            self.report_progress(0.56, "相似度比对完成，正在保存库存...")

            # 辅助函数：判断单元格是否为空值或空字符串
            def is_cell_empty(val):
                if pd.isna(val):
                    return True
                val_str = str(val).strip().lower()
                return val_str in ['', 'nan', 'none', 'null', '-']

            # 优先从输入表格 (df_input) 中读取可能已经存在/手动填好的 '翻译英文' 和 'AI分类'
            for idx, r in enumerate(results):
                if '翻译英文' in df_input.columns:
                    val_trans = df_input.iloc[idx]['翻译英文']
                    if not is_cell_empty(val_trans):
                        r['翻译英文'] = str(val_trans).strip()
                if 'AI分类' in df_input.columns:
                    val_class = df_input.iloc[idx]['AI分类']
                    if not is_cell_empty(val_class):
                        r['AI分类'] = str(val_class).strip()

            # 4. 提取需要翻译或 AI 分类的文案进行批量处理 (包含新文案，以及库中缺失翻译/分类的已存在文案)
            
            # --- 批量翻译缺失英文的文案 ---
            if translate_mode and translate_mode != "none":
                target_lang = "English" if translate_mode == "en" else "Polish"
                self.report_progress(0.60, f"正在将缺失翻译的文案批量翻译为 {target_lang}...")
                
                # 过滤出唯一且没有翻译内容的进行翻译（按分配编号去重）
                unique_new_by_id = {}
                for r in results:
                    t_val = str(r['文案内容']).strip()
                    if t_val and t_val.lower() != 'nan' and r['分配编号'] not in unique_new_by_id:
                        if not r.get('翻译英文') or str(r.get('翻译英文')).strip() == "":
                            unique_new_by_id[r['分配编号']] = t_val
                
                if unique_new_by_id:
                    unique_ids = list(unique_new_by_id.keys())
                    unique_texts_to_trans = [unique_new_by_id[uid] for uid in unique_ids]
                    
                    # 翻译返回完整译文，响应体积远大于分类（分类只返回短类别名）
                    # 为防止超时断连，翻译批次大小上限为 50 条
                    translate_batch_size = min(int(ai_batch_size), 50)

                    def trans_progress_cb_match(cur_b, tot_b):
                        p = 0.60 + (cur_b / max(tot_b, 1)) * 0.12
                        self.report_progress(p, f"正在翻译文案 ({cur_b}/{tot_b} 批)...")

                    translated_unique = self.translate_texts_with_gemini(
                        unique_texts_to_trans,
                        target_lang,
                        translate_api_key,
                        translate_model,
                        translate_batch_size,
                        int(ai_concurrency),
                        progress_callback=trans_progress_cb_match,
                        ai_platform=translate_platform,
                        ai_proxy=translate_proxy
                    )
                    
                    id_to_translated = dict(zip(unique_ids, translated_unique))
                    # 回填到结果集中
                    for r in results:
                        if not r.get('翻译英文') or str(r.get('翻译英文')).strip() == "":
                            r['翻译英文'] = id_to_translated.get(r['分配编号'], "")
            
            # --- 批量 AI 分类缺失分类的文案 ---
            if ai_classify_enable:
                self.report_progress(0.75, "正在对缺失分类的文案进行 AI 智能分类...")
                
                unique_new_by_id_for_class = {}
                for r in results:
                    if not r.get('AI分类') or str(r.get('AI分类')).strip() == "":
                        if r['分配编号'] not in unique_new_by_id_for_class:
                            # 优先使用翻译后的英文进行分类，否则使用原始文案
                            text_for_class = r.get('翻译英文', '')
                            if not text_for_class or text_for_class.strip() == '':
                                text_for_class = r['文案内容']
                            unique_new_by_id_for_class[r['分配编号']] = text_for_class
                            
                if unique_new_by_id_for_class:
                    unique_ids_class = list(unique_new_by_id_for_class.keys())
                    unique_texts_to_class = [unique_new_by_id_for_class[uid] for uid in unique_ids_class]
                    
                    classified_unique = self.classify_texts_with_gemini(
                        unique_texts_to_class,
                        ai_api_key,
                        ai_rules,
                        ai_model,
                        int(ai_batch_size),
                        int(ai_concurrency),
                        ai_platform=translate_platform,
                        ai_proxy=translate_proxy
                    )
                    
                    id_to_classified = dict(zip(unique_ids_class, classified_unique))
                    # 回填到结果集中
                    for r in results:
                        if not r.get('AI分类') or str(r.get('AI分类')).strip() == "":
                            r['AI分类'] = id_to_classified.get(r['分配编号'], "其他")

            # --- 将入库表格写入的所有内容，同步更新/录入库存表格 ---
            inv_id_col = self.matcher.find_id_column(self.matcher.df_inventory.columns) or '编号'
            for idx_input, r in enumerate(results):
                new_id = r['分配编号']
                if not new_id or new_id == "N/A":
                    continue
                
                # 查找库存中匹配该编号的行（无论是新增加的，还是原本已存在的）
                matching_indices = self.matcher.df_inventory[self.matcher.df_inventory[inv_id_col].astype(str).str.strip() == str(new_id).strip()].index
                
                for idx_inv in matching_indices:
                    # 1. 写入匹配结果和过渡处理字段
                    self.matcher.df_inventory.at[idx_inv, '翻译英文'] = r.get('翻译英文', '')
                    self.matcher.df_inventory.at[idx_inv, 'AI分类'] = r.get('AI分类', '')
                    self.matcher.df_inventory.at[idx_inv, '匹配状态'] = r.get('匹配状态', '')
                    self.matcher.df_inventory.at[idx_inv, '相似度'] = r.get('相似度', '')
                    self.matcher.df_inventory.at[idx_inv, '最相似文案'] = r.get('最相似文案', '')
                    self.matcher.df_inventory.at[idx_inv, '入库时间'] = r.get('入库时间', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                    
                    # 2. 写入输入文件中的所有其他备注或自定义列（例如 中文, 备注1, 备注2 等）
                    input_row = df_input.iloc[idx_input]
                    for col in self.matcher.df_inventory.columns:
                        # 排除系统级控制列
                        if col not in ['翻译英文', 'AI分类', '匹配状态', '相似度', '最相似文案', '入库时间', '匹配次数', inv_id_col]:
                            if col in input_row:
                                val = input_row[col]
                                if pd.isna(val):
                                    val = ""
                                self.matcher.df_inventory.at[idx_inv, col] = val
            
            # 重新保存库存文件以固化所有新数据与更新
            self.matcher.save_inventory()

            # 5. 导出结果至原目录
            self.report_progress(0.92, "正在写入并保存结果表格...")
            df_output = df_input.copy()
            
            # 自定义写入列逻辑：若为新建列则默认使用 '分配编号'，否则覆盖选中列
            actual_write_col = write_col_name
            if not actual_write_col or actual_write_col == "NEW_COL" or actual_write_col == "新建 '分配编号' 列":
                actual_write_col = '分配编号'
                
            df_output[actual_write_col] = [r['分配编号'] for r in results]
            df_output['匹配状态'] = [r['匹配状态'] for r in results]
            df_output['相似度'] = [r['相似度'] for r in results]
            df_output['最相似文案'] = [r['最相似文案'] for r in results]
            df_output['翻译英文'] = [r.get('翻译英文', '') for r in results]
            df_output['AI分类'] = [r.get('AI分类', '') for r in results]
            df_output['入库时间'] = [r.get('入库时间', datetime.now().strftime('%Y-%m-%d %H:%M:%S')) for r in results]

            if use_google_input:
                self.report_progress(0.95, "正在将比对结果回写至谷歌表格...")
                df_to_save = df_output.fillna("").astype(str)
                values = [df_to_save.columns.tolist()] + df_to_save.values.tolist()
                
                worksheet_input.clear()
                worksheet_input.update(values, 'A1')
                out_path = google_input_url
            else:
                input_dir, input_name = os.path.split(input_path)
                name_part, ext_part = os.path.splitext(input_name)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                out_filename = f"{name_part}_比对结果_{timestamp}.xlsx"
                out_path = os.path.join(input_dir, out_filename)

                self.report_progress(0.95, "正在写入结果表格磁盘文件...")
                df_output.to_excel(out_path, index=False)

            self.report_progress(0.98, "正在更新界面预览数据...")
            matched_count = sum(1 for r in results if "已存在" in r['匹配状态'])
            new_count = sum(1 for r in results if r['匹配状态'] == "新文案")

            # 注入入库时间到 results 列表中供前端预览
            for r in results:
                r['入库时间'] = r.get('入库时间', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

            # 传递前 200 条用于前端表格展示
            preview_results = results[:200]
            # 通知前端渲染
            js_cmd = f"window.showResults({json.dumps(preview_results, ensure_ascii=False)}, {matched_count}, {new_count}, {json.dumps(out_path.replace('\\', '/'), ensure_ascii=False)});"
            self._window.evaluate_js(js_cmd)

        except Exception as e:
            self._window.evaluate_js(f"window.showError({json.dumps(str(e), ensure_ascii=False)});")

    def report_progress(self, progress, msg):
        self._window.evaluate_js(f"window.updateProgress({progress}, {json.dumps(msg, ensure_ascii=False)});")

    def log_message(self, level, text):
        """
        向前端控制台/日志框打印日志。
        level 可选: 'info', 'success', 'warning', 'error', 'system'
        """
        if not self._window:
            return
        js_cmd = f"window.addLog('{level}', {json.dumps(text, ensure_ascii=False)});"
        try:
            self._window.evaluate_js(js_cmd)
        except Exception as e:
            print(f"Failed to log to UI: {e}")

    def translate_texts_with_gemini(self, texts, target_lang_name, api_key, model_name, batch_size, concurrency,
                                    progress_callback=None, ai_platform="google-ai-studio", ai_base_url="", ai_proxy=""):
        """
        使用 Gemini API 多线程并发批量翻译文本列表
        """
        translations = [None] * len(texts)
        
        # 解析代理设置
        proxies = None
        if ai_proxy and ai_proxy.strip():
            p_val = ai_proxy.strip()
            proxies = {"http": p_val, "https": p_val}
            self.log_message('info', f'[AI翻译] 使用手动代理: {p_val}')
        else:
            import urllib.request
            detected = urllib.request.getproxies()
            if detected:
                proxies = detected
                self.log_message('info', f'[AI翻译] 自动检测到系统代理: {proxies}')
            else:
                self.log_message('info', '[AI翻译] 未检测到代理，直接发起连接。')
        
        # 解析 Base URL 与 API 请求 Endpoint
        if not ai_base_url:
            if ai_platform == "vertex-ai":
                base_url = "https://aiplatform.googleapis.com"
            else:
                base_url = "https://generativelanguage.googleapis.com"
        else:
            base_url = ai_base_url.rstrip('/')

        if ai_platform == "vertex-ai":
            url = f"{base_url}/v1/publishers/google/models/{model_name}:generateContent?key={api_key}"
        else:
            url = f"{base_url}/v1beta/models/{model_name}:generateContent?key={api_key}"

        # 划分批次
        batches = []
        batch_indices = []
        for i in range(0, len(texts), batch_size):
            batch_indices.append(list(range(i, min(i + batch_size, len(texts)))))
            batches.append(texts[i : i + batch_size])
            
        total_batches = len(batches)
        if total_batches == 0:
            return translations
            
        completed_batches = 0
        self.log_message('system', f'--- 开始批量 AI 翻译流程 (目标语言: {target_lang_name}) ---')
        self.log_message('info', f'[AI翻译] 总计文本: {len(texts)} 条，分 {total_batches} 批处理，每批: {batch_size} 条，并发数: {concurrency}')
        self.log_message('info', f'[AI翻译] 平台: {ai_platform}, 目标模型: {model_name}')
        masked_url_trans = url.split("?")[0] + "?key=***"
        self.log_message('info', f'[AI翻译] 请求端点: {masked_url_trans}')

        def worker(batch_idx, batch_texts):
            # 将本批文案合并为带编号的纯文本块，一次性传给 AI
            numbered_input = "\n".join(f"[{i+1}] {t}" for i, t in enumerate(batch_texts))

            prompt = f"""You are a professional translator. Translate each numbered item below to {target_lang_name}.

Rules:
1. Maintain the original tone and meaning exactly.
2. Keep product names or special terms unchanged if appropriate.
3. Return EXACTLY the same number of items as the input.
4. Output ONLY the numbered translations in the same format as the input, one per line. No extra text, no markdown.

Format example:
[1] translated text one
[2] translated text two

Texts to translate:
{numbered_input}"""

            import time, re
            max_retries = 5
            retry_delay = 2
            headers = {"Content-Type": "application/json"}
            payload = {
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.0}
            }

            response = None
            for attempt in range(max_retries):
                try:
                    self.log_message('info', f'[翻译批次 {batch_idx + 1}/{total_batches}] 正在发送请求 (第 {attempt + 1}/{max_retries} 次尝试，共 {len(batch_texts)} 条)...')
                    response = requests.post(url, headers=headers, json=payload, proxies=proxies, timeout=180)
                    if response.status_code != 200:
                        if response.status_code == 429 and attempt < max_retries - 1:
                            # 429 配额耗尽：使用指数退避，首次等待 30 秒
                            wait_secs = min(30 * (2 ** attempt), 300)
                            self.log_message('warning', f'[翻译批次 {batch_idx + 1}/{total_batches}] API 配额耗尽 (429)，等待 {wait_secs} 秒后重试 ({attempt + 1}/{max_retries})...')
                            time.sleep(wait_secs)
                            continue
                        if response.status_code in [500, 502, 503, 504] and attempt < max_retries - 1:
                            self.log_message('warning', f'[翻译批次 {batch_idx + 1}/{total_batches}] 服务器返回 {response.status_code}，{retry_delay} 秒后重试...')
                            time.sleep(retry_delay)
                            continue
                        try:
                            err_msg = response.json().get("error", {}).get("message", response.text)
                        except Exception:
                            err_msg = response.text
                        raise RuntimeError(f"API 拒绝请求 (状态码 {response.status_code}):\n{err_msg}")
                    break  # 请求成功，跳出重试
                except (requests.exceptions.RequestException, RuntimeError) as e:
                    if attempt < max_retries - 1:
                        self.log_message('warning', f'[翻译批次 {batch_idx + 1}/{total_batches}] 请求异常: {e}，{retry_delay} 秒后重试...')
                        time.sleep(retry_delay)
                    else:
                        raise

            # --- 解析回传的带编号纯文本 ---
            try:
                resp_data = response.json()
                text_out = resp_data['candidates'][0]['content']['parts'][0]['text'].strip()
            except Exception as e:
                raise RuntimeError(f"解析 API 响应失败: {e}")

            # 用正则从回传文本中提取 [N] 内容
            parsed = {}
            for line in text_out.splitlines():
                m = re.match(r'^\[(\d+)\]\s*(.*)', line.strip())
                if m:
                    parsed[int(m.group(1))] = m.group(2).strip()

            if len(parsed) == len(batch_texts):
                results_list = [parsed.get(i + 1, str(batch_texts[i])) for i in range(len(batch_texts))]
                self.log_message('success', f'[翻译批次 {batch_idx + 1}/{total_batches}] 带编号解析成功，共 {len(results_list)} 条。')
                return batch_idx, results_list

            # 部分解析成功时也尽量填充
            if parsed:
                self.log_message('warning', f'[翻译批次 {batch_idx + 1}/{total_batches}] 部分解析成功 ({len(parsed)}/{len(batch_texts)})，缺失项使用原文填充。')
                results_list = [parsed.get(i + 1, str(batch_texts[i])) for i in range(len(batch_texts))]
                return batch_idx, results_list

            # 完全解析失败：降级为逐条单独请求
            self.log_message('warning', f'[翻译批次 {batch_idx + 1}/{total_batches}] 整批解析失败，降级为逐条翻译...')
            backup_results = []
            for sub_idx, text in enumerate(batch_texts):
                if not text or not str(text).strip():
                    backup_results.append("")
                    continue
                single_prompt = f"Translate the following text to {target_lang_name}. Output ONLY the translated text, no quotes or explanation:\n\n{text}"
                payload_single = {
                    "contents": [{"role": "user", "parts": [{"text": single_prompt}]}],
                    "generationConfig": {"temperature": 0.0}
                }
                try:
                    self.log_message('info', f'[翻译批次 {batch_idx + 1}] 降级单条 {sub_idx + 1}/{len(batch_texts)}...')
                    res = requests.post(url, headers=headers, json=payload_single, proxies=proxies, timeout=60)
                    if res.status_code == 200:
                        out = res.json()['candidates'][0]['content']['parts'][0]['text'].strip()
                        backup_results.append(out)
                    else:
                        try:
                            err_msg = res.json().get("error", {}).get("message", res.text)
                        except Exception:
                            err_msg = res.text
                        raise RuntimeError(f"API 拒绝请求 (单条 {res.status_code}):\n{err_msg}")
                except Exception as e:
                    if "API 拒绝请求" in str(e):
                        raise
                    self.log_message('warning', f'[翻译批次 {batch_idx + 1}] 单条异常: {e}，使用原文。')
                    backup_results.append(str(text))
            self.log_message('success', f'[翻译批次 {batch_idx + 1}/{total_batches}] 降级逐条翻译完成。')
            return batch_idx, backup_results

        # 多线程并发执行
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            future_to_batch = {
                executor.submit(worker, idx, batch): idx 
                for idx, batch in enumerate(batches)
            }
            
            for future in as_completed(future_to_batch):
                idx, results = future.result()
                indices = batch_indices[idx]
                for offset, val in enumerate(results):
                    if offset < len(indices):
                        translations[indices[offset]] = val
                
                completed_batches += 1
                if progress_callback:
                    progress_callback(completed_batches, total_batches)

        for i in range(len(translations)):
            if translations[i] is None:
                translations[i] = str(texts[i])
                
        self.log_message('system', f'--- 批量 AI 翻译完成 ---')
        return translations

    def classify_texts_with_gemini(self, texts, api_key, rules, model_name, batch_size, concurrency, progress_callback=None,
                                   ai_platform="google-ai-studio", ai_base_url="", ai_proxy=""):
        """
        多线程并发批量调用 Gemini REST API 接口分类文本
        """
        classifications = [None] * len(texts)
        
        # 解析代理设置
        proxies = None
        if ai_proxy and ai_proxy.strip():
            p_val = ai_proxy.strip()
            proxies = {"http": p_val, "https": p_val}
            self.log_message('info', f'[AI分类] 使用手动代理: {p_val}')
        else:
            import urllib.request
            detected = urllib.request.getproxies()
            if detected:
                proxies = detected
                self.log_message('info', f'[AI分类] 自动检测到系统代理: {proxies}')
            else:
                self.log_message('info', '[AI分类] 未检测到代理，直接发起连接。')
        
        # 解析 Base URL 与 API 请求 Endpoint
        if not ai_base_url:
            if ai_platform == "vertex-ai":
                base_url = "https://aiplatform.googleapis.com"
            else:
                base_url = "https://generativelanguage.googleapis.com"
        else:
            base_url = ai_base_url.rstrip('/')

        if ai_platform == "vertex-ai":
            url = f"{base_url}/v1/publishers/google/models/{model_name}:generateContent?key={api_key}"
        else:
            url = f"{base_url}/v1beta/models/{model_name}:generateContent?key={api_key}"

        # 将输入划分为批次
        batches = []
        batch_indices = []
        
        for i in range(0, len(texts), batch_size):
            batch_indices.append(list(range(i, min(i + batch_size, len(texts)))))
            batches.append(texts[i : i + batch_size])
            
        total_batches = len(batches)
        if total_batches == 0:
            return classifications
            
        completed_batches = 0
        
        self.log_message('system', f'--- 开始批量 AI 智能分类流程 ---')
        self.log_message('info', f'[AI分类] 总计文本: {len(texts)} 条，分 {total_batches} 批处理，每批: {batch_size} 条，并发数: {concurrency}')
        self.log_message('info', f'[AI分类] 平台: {ai_platform}, 目标模型: {model_name}')
        masked_url = url.split("?")[0] + "?key=***"
        self.log_message('info', f'[AI分类] 请求端点: {masked_url}')

        def worker(batch_idx, batch_texts):
            # 将本批文案合并为带编号的纯文本块，一次性传给 AI
            numbered_input = "\n".join(f"[{i+1}] {t}" for i, t in enumerate(batch_texts))

            prompt = f"""你是一个专业的文本分类 AI 助手。请根据以下分类规则，对给出的每条带编号文案进行分类。

【分类规则和优先级】
{rules}

【输出格式要求】
按照输入的编号顺序，每行输出一条分类结果，格式为：
[编号] 类别名称

示例：
[1] 借势贴
[2] 祷告
[3] 其他

注意：
- 必须输出与输入完全相同数量的行
- 类别名称必须是分类规则中提及的类别（如"借势贴"、"主再来"、"悔改类"等）
- 如无法匹配，输出"其他"
- 不要输出任何多余的解释文字

【待分类文案】
{numbered_input}"""

            import time, re
            max_retries = 5
            retry_delay = 2
            headers = {"Content-Type": "application/json"}
            payload = {
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.0}
            }

            response = None
            for attempt in range(max_retries):
                try:
                    self.log_message('info', f'[分类批次 {batch_idx + 1}/{total_batches}] 正在发送请求 (第 {attempt + 1}/{max_retries} 次尝试，共 {len(batch_texts)} 条)...')
                    response = requests.post(url, headers=headers, json=payload, proxies=proxies, timeout=180)
                    if response.status_code != 200:
                        if response.status_code == 429 and attempt < max_retries - 1:
                            wait_secs = min(30 * (2 ** attempt), 300)
                            self.log_message('warning', f'[分类批次 {batch_idx + 1}/{total_batches}] API 配额耗尽 (429)，等待 {wait_secs} 秒后重试 ({attempt + 1}/{max_retries})...')
                            time.sleep(wait_secs)
                            continue
                        if response.status_code in [500, 502, 503, 504] and attempt < max_retries - 1:
                            self.log_message('warning', f'[分类批次 {batch_idx + 1}/{total_batches}] 服务器返回 {response.status_code}，{retry_delay} 秒后重试...')
                            time.sleep(retry_delay)
                            continue
                        try:
                            err_msg = response.json().get("error", {}).get("message", response.text)
                        except Exception:
                            err_msg = response.text
                        raise RuntimeError(f"API 拒绝请求 (状态码 {response.status_code}):\n{err_msg}")
                    break  # 请求成功，跳出重试
                except (requests.exceptions.RequestException, RuntimeError) as e:
                    if attempt < max_retries - 1:
                        self.log_message('warning', f'[分类批次 {batch_idx + 1}/{total_batches}] 请求异常: {e}，{retry_delay} 秒后重试...')
                        time.sleep(retry_delay)
                    else:
                        raise

            # --- 解析回传的带编号纯文本 ---
            try:
                resp_data = response.json()
                text_out = resp_data['candidates'][0]['content']['parts'][0]['text'].strip()
            except Exception as e:
                raise RuntimeError(f"解析 API 响应失败: {e}")

            # 用正则从回传文本中提取 [N] 内容
            parsed = {}
            for line in text_out.splitlines():
                m = re.match(r'^\[(\d+)\]\s*(.*)', line.strip())
                if m:
                    parsed[int(m.group(1))] = m.group(2).strip()

            if len(parsed) == len(batch_texts):
                results_list = [parsed.get(i + 1, "其他") for i in range(len(batch_texts))]
                self.log_message('success', f'[分类批次 {batch_idx + 1}/{total_batches}] 带编号解析成功，共 {len(results_list)} 条。')
                return batch_idx, results_list

            # 部分解析成功时也尽量填充
            if parsed:
                self.log_message('warning', f'[分类批次 {batch_idx + 1}/{total_batches}] 部分解析成功 ({len(parsed)}/{len(batch_texts)})，缺失项填充"其他"。')
                results_list = [parsed.get(i + 1, "其他") for i in range(len(batch_texts))]
                return batch_idx, results_list

            # 完全解析失败：降级为逐条单独请求
            self.log_message('warning', f'[分类批次 {batch_idx + 1}/{total_batches}] 整批解析失败，降级为逐条分类...')
            backup_results = []
            for sub_idx, text in enumerate(batch_texts):
                if not text or not str(text).strip():
                    backup_results.append("其他")
                    continue
                single_prompt = f"""请根据以下规则对文案进行分类。直接输出最匹配的分类名称即可，不要有任何其他解释。

【分类规则】
{rules}

【待分类文案】
{text}"""
                payload_single = {
                    "contents": [{"role": "user", "parts": [{"text": single_prompt}]}],
                    "generationConfig": {"temperature": 0.0}
                }
                try:
                    self.log_message('info', f'[分类批次 {batch_idx + 1}] 降级单条 {sub_idx + 1}/{len(batch_texts)}...')
                    res = requests.post(url, headers=headers, json=payload_single, proxies=proxies, timeout=60)
                    if res.status_code == 200:
                        out = res.json()['candidates'][0]['content']['parts'][0]['text'].strip()
                        backup_results.append(out[:30])
                    else:
                        try:
                            err_msg = res.json().get("error", {}).get("message", res.text)
                        except Exception:
                            err_msg = res.text
                        raise RuntimeError(f"API 拒绝请求 (单条 {res.status_code}):\n{err_msg}")
                except Exception as e:
                    if "API 拒绝请求" in str(e):
                        raise
                    self.log_message('warning', f'[分类批次 {batch_idx + 1}] 单条异常: {e}，填充"其他"。')
                    backup_results.append("其他")
            self.log_message('success', f'[分类批次 {batch_idx + 1}/{total_batches}] 降级逐条分类完成。')
            return batch_idx, backup_results

        # 多线程并发执行
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            future_to_batch = {
                executor.submit(worker, idx, batch): idx 
                for idx, batch in enumerate(batches)
            }
            
            for future in as_completed(future_to_batch):
                idx, results = future.result()
                indices = batch_indices[idx]
                for offset, val in enumerate(results):
                    if offset < len(indices):
                        classifications[indices[offset]] = val
                
                completed_batches += 1
                if progress_callback:
                    progress_callback(completed_batches, total_batches)

        for i in range(len(classifications)):
            if classifications[i] is None:
                classifications[i] = "其他"
                
        self.log_message('system', '--- 批量 AI 智能分类完成 ---')
        return classifications

    def run_translation(self, input_path, col_name, target_lang, api_key, platform, model_name,
                        batch_size, concurrency, output_col_name,
                        use_google_input=False, google_input_url="", google_input_name="", google_creds_path="",
                        proxy=""):
        """
        异步运行独立翻译任务（不做匹配，不做分类）
        """
        threading.Thread(
            target=self._run_translation_worker,
            args=(input_path, col_name, target_lang, api_key, platform, model_name,
                  batch_size, concurrency, output_col_name,
                  use_google_input, google_input_url, google_input_name, google_creds_path, proxy),
            daemon=True
        ).start()
        return {"status": "started"}

    def _run_translation_worker(self, input_path, col_name, target_lang, api_key, platform, model_name,
                                batch_size, concurrency, output_col_name,
                                use_google_input=False, google_input_url="", google_input_name="", google_creds_path="",
                                proxy=""):
        try:
            self.report_progress(0.05, "正在载入文案表格...")
            self.log_message('system', '--- 独立翻译任务开始 ---')

            worksheet_input = None
            # 读取数据
            if use_google_input:
                from google.oauth2.service_account import Credentials
                import gspread
                scopes = [
                    'https://www.googleapis.com/auth/spreadsheets',
                    'https://www.googleapis.com/auth/drive'
                ]
                credentials = Credentials.from_service_account_file(google_creds_path, scopes=scopes)
                gc = gspread.authorize(credentials)
                sh = gc.open_by_url(google_input_url)
                if google_input_name:
                    worksheet_input = sh.worksheet(google_input_name)
                else:
                    worksheet_input = sh.get_worksheet(0)
                data = worksheet_input.get_all_values()
                if not data:
                    raise ValueError("谷歌待翻译工作表为空！")
                headers = data[0]
                rows = data[1:]
                df_input = pd.DataFrame(rows, columns=headers)
            else:
                if input_path.endswith('.csv'):
                    try:
                        df_input = pd.read_csv(input_path, encoding='utf-8')
                    except UnicodeDecodeError:
                        df_input = pd.read_csv(input_path, encoding='gbk')
                else:
                    df_input = pd.read_excel(input_path)

            # 确定源文案列
            target_col = col_name if col_name in df_input.columns else (df_input.columns[0] if len(df_input.columns) > 0 else None)
            if target_col is None:
                raise ValueError("未能在输入文件中找到可用的文案内容列！")

            texts = df_input[target_col].tolist()
            total_count = len(texts)
            self._window.evaluate_js(f"window.updateTotalCount({total_count});")

            if total_count == 0:
                raise ValueError("导入的表格为空，没有可翻译的记录！")

            self.log_message('info', f'共读取 {total_count} 条文案，目标语言: {target_lang}，写入列: {output_col_name}')

            # 目标语言名称映射
            lang_name_map = {"en": "English", "pl": "Polish"}
            target_lang_name = lang_name_map.get(target_lang, "English")

            # 过滤出非空文本才翻译
            non_empty_indices = [i for i, t in enumerate(texts) if t and str(t).strip() and str(t).lower() not in ('nan', 'none', '')]
            non_empty_texts = [str(texts[i]).strip() for i in non_empty_indices]

            def trans_progress_cb(cur_b, tot_b):
                p = 0.10 + (cur_b / tot_b) * 0.80
                self.report_progress(p, f"正在翻译 ({cur_b}/{tot_b} 批)...")
                self.log_message('info', f'[翻译进度] 已完成: {cur_b}/{tot_b} 批')

            translated_non_empty = []
            if non_empty_texts:
                translate_batch_size = min(int(batch_size), 50)
                translated_non_empty = self.translate_texts_with_gemini(
                    non_empty_texts,
                    target_lang_name,
                    api_key,
                    model_name,
                    translate_batch_size,
                    int(concurrency),
                    progress_callback=trans_progress_cb,
                    ai_platform=platform,
                    ai_proxy=proxy
                )

            # 组装完整译文列表（空行保留空字符串）
            translated_all = [""] * total_count
            for list_idx, orig_idx in enumerate(non_empty_indices):
                if list_idx < len(translated_non_empty):
                    translated_all[orig_idx] = translated_non_empty[list_idx]

            self.report_progress(0.92, "正在写入并保存翻译结果...")
            df_output = df_input.copy()

            # 确定写入列名（默认"翻译英文"）
            write_col = output_col_name.strip() if output_col_name and output_col_name.strip() else "翻译英文"
            df_output[write_col] = translated_all

            if use_google_input and worksheet_input:
                self.report_progress(0.95, "正在将翻译结果回写至谷歌表格...")
                df_to_save = df_output.fillna("").astype(str)
                values = [df_to_save.columns.tolist()] + df_to_save.values.tolist()
                worksheet_input.clear()
                worksheet_input.update(values, 'A1')
                out_path = google_input_url
            else:
                input_dir, input_name = os.path.split(input_path)
                name_part, ext_part = os.path.splitext(input_name)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                out_filename = f"{name_part}_翻译_{timestamp}.xlsx"
                out_path = os.path.join(input_dir, out_filename)
                self.report_progress(0.95, "正在写入翻译结果磁盘文件...")
                df_output.to_excel(out_path, index=False)

            self.report_progress(0.98, "正在更新界面预览数据...")

            # 构造预览结果（只展示前 200 条）
            results = []
            for i, text in enumerate(texts):
                results.append({
                    '文案内容': str(text),
                    '分配编号': 'N/A',
                    '匹配状态': '已翻译',
                    '相似度': '-',
                    '最相似文案': '-',
                    '翻译英文': translated_all[i],
                    'AI分类': ''
                })

            js_cmd = f"window.showTranslationResults({json.dumps(results[:200], ensure_ascii=False)}, {total_count}, {json.dumps(out_path.replace(chr(92), '/'), ensure_ascii=False)});"
            self._window.evaluate_js(js_cmd)
            self.log_message('success', f'独立翻译完成！结果写入列 "{write_col}"，已保存文件。')
            self.log_message('system', '--- 独立翻译任务结束 ---')

        except Exception as e:
            self.log_message('error', f'翻译任务发生致命错误: {str(e)}')
            self._window.evaluate_js(f"window.showError({json.dumps(str(e), ensure_ascii=False)});")

    def run_ai_classification(self, input_path, col_name, use_google_input, google_input_url, google_input_name, google_creds_path,
                              ai_api_key, ai_model, ai_batch_size, ai_concurrency, ai_col_name, ai_rules,
                              ai_platform="google-ai-studio", ai_base_url="", ai_proxy="", translate_mode="none"):
        """
        异步运行 AI 智能分类，不比对数据库
        """
        threading.Thread(
            target=self._run_ai_classification_worker,
            args=(input_path, col_name, use_google_input, google_input_url, google_input_name, google_creds_path,
                  ai_api_key, ai_model, ai_batch_size, ai_concurrency, ai_col_name, ai_rules, ai_platform, ai_base_url, ai_proxy, translate_mode),
            daemon=True
        ).start()
        return {"status": "started"}

    def _run_ai_classification_worker(self, input_path, col_name, use_google_input, google_input_url, google_input_name, google_creds_path,
                                      ai_api_key, ai_model, ai_batch_size, ai_concurrency, ai_col_name, ai_rules,
                                      ai_platform="google-ai-studio", ai_base_url="", ai_proxy="", translate_mode="none"):
        try:
            self.report_progress(0.05, "正在载入文案表格...")
            self.log_message('info', '正在读取文案表格数据...')
            
            # 读取数据
            if use_google_input:
                from google.oauth2.service_account import Credentials
                import gspread
                
                scopes = [
                    'https://www.googleapis.com/auth/spreadsheets',
                    'https://www.googleapis.com/auth/drive'
                ]
                credentials = Credentials.from_service_account_file(google_creds_path, scopes=scopes)
                gc = gspread.authorize(credentials)
                sh = gc.open_by_url(google_input_url)
                
                if google_input_name:
                    worksheet_input = sh.worksheet(google_input_name)
                else:
                    worksheet_input = sh.get_worksheet(0)
                    
                data = worksheet_input.get_all_values()
                if not data or len(data) == 0:
                    raise ValueError("谷歌待分类工作表为空，没有可读取的记录！")
                    
                headers = data[0]
                rows = data[1:]
                df_input = pd.DataFrame(rows, columns=headers)
            else:
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

            # 翻译优化逻辑
            final_classify_texts = new_texts
            if translate_mode and translate_mode != "none":
                target_lang = "English" if translate_mode == "en" else "Polish"
                self.report_progress(0.12, f"正在将文案批量翻译为 {target_lang}...")
                
                non_empty_indices = [idx for idx, t in enumerate(new_texts) if t and str(t).strip() and str(t).lower() != 'nan']
                non_empty_texts = [str(new_texts[idx]).strip() for idx in non_empty_indices]
                
                translated_non_empty = []
                if non_empty_texts:
                    translated_non_empty = self.translate_texts_with_gemini(
                        non_empty_texts,
                        target_lang,
                        ai_api_key,
                        ai_model,
                        int(ai_batch_size),
                        int(ai_concurrency),
                        ai_platform=ai_platform,
                        ai_proxy=ai_proxy
                    )
                
                translated_texts = []
                t_idx = 0
                for t in new_texts:
                    if t and str(t).strip() and str(t).lower() != 'nan':
                        translated_texts.append(translated_non_empty[t_idx])
                        t_idx += 1
                    else:
                        translated_texts.append("")
                        
                translated_col_name = "翻译英文"
                df_input[translated_col_name] = translated_texts
                final_classify_texts = translated_texts

            # 自动去重优化
            id_col = None
            for col in df_input.columns:
                if str(col).strip() in ['分配编号', '编号', 'id', 'ID']:
                    if df_input[col].dropna().astype(str).str.strip().any():
                        id_col = col
                        break

            unique_texts = []
            seen = set()
            id_to_representative_text = {}
            
            for idx, row in df_input.iterrows():
                val_id = str(row[id_col]).strip() if id_col and pd.notna(row[id_col]) else ""
                val_text = str(final_classify_texts[idx]).strip() if idx < len(final_classify_texts) else ""
                if not val_text or val_text.lower() == 'nan':
                    continue
                
                if val_id and val_id != "nan" and val_id != "-":
                    if val_id not in id_to_representative_text:
                        id_to_representative_text[val_id] = val_text
                        if val_text not in seen:
                            seen.add(val_text)
                            unique_texts.append(val_text)
                else:
                    if val_text not in seen:
                        seen.add(val_text)
                        unique_texts.append(val_text)

            unique_count = len(unique_texts)
            saved_calls = total_count - unique_count
            
            if id_col:
                self.log_message('success', f'检测到可用编号列 "{id_col}"，已启用混合去重优化。')
            else:
                self.log_message('success', f'未检测到有效编号，已启用文本去重优化。')
            self.log_message('system', f'[优化控制] 总计 {total_count} 行文案。唯一处理数: {unique_count}，重复处理数: {saved_calls}。本次分类仅提交去重代表文案，为您省去了 {saved_calls} 次重复的 AI 请求！')

            if unique_count == 0:
                ai_classifications = ["其他"] * total_count
            else:
                def ai_progress_cb(cur_b, tot_b):
                    p = 0.15 + (cur_b / tot_b) * 0.70
                    self.report_progress(p, f"正在进行多线程 AI 智能分类 ({cur_b}/{tot_b} 批)...")
                    self.log_message('info', f'[分类进度] 已完成: {cur_b}/{tot_b} 批 ({int((cur_b/tot_b)*100)}%)')
                    
                unique_classifications = self.classify_texts_with_gemini(
                    unique_texts,
                    ai_api_key,
                    ai_rules,
                    ai_model,
                    int(ai_batch_size),
                    int(ai_concurrency),
                    progress_callback=ai_progress_cb,
                    ai_platform=ai_platform,
                    ai_base_url=ai_base_url,
                    ai_proxy=ai_proxy
                )

                # 建立 文本 -> 分类 的映射字典
                text_to_class = {}
                for text, classification in zip(unique_texts, unique_classifications):
                    text_to_class[text] = classification

                # 建立 ID -> 分类 的映射字典
                id_to_class = {}
                for kid, val_text in id_to_representative_text.items():
                    if val_text in text_to_class:
                        id_to_class[kid] = text_to_class[val_text]

                ai_classifications = []
                for idx, row in df_input.iterrows():
                    val_id = str(row[id_col]).strip() if id_col and pd.notna(row[id_col]) else ""
                    val_text = str(final_classify_texts[idx]).strip() if idx < len(final_classify_texts) else ""
                    
                    if not val_text or val_text.lower() == 'nan':
                        ai_classifications.append("其他")
                    elif val_id and val_id != "nan" and val_id != "-" and val_id in id_to_class:
                        ai_classifications.append(id_to_class[val_id])
                    else:
                        ai_classifications.append(text_to_class.get(val_text, "其他"))

            self.report_progress(0.88, "正在写入并保存分类结果...")
            df_output = df_input.copy()
            col_write_ai = ai_col_name if ai_col_name else "AI分类"
            df_output[col_write_ai] = ai_classifications
            
            if use_google_input:
                self.report_progress(0.92, "正在将 AI 分类结果回写至谷歌表格...")
                self.log_message('info', '正在回写数据到谷歌工作表...')
                df_to_save = df_output.fillna("").astype(str)
                values = [df_to_save.columns.tolist()] + df_to_save.values.tolist()
                
                worksheet_input.clear()
                worksheet_input.update(values, 'A1')
                out_path = google_input_url
            else:
                input_dir, input_name = os.path.split(input_path)
                name_part, ext_part = os.path.splitext(input_name)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                out_filename = f"{name_part}_AI分类_{timestamp}.xlsx"
                out_path = os.path.join(input_dir, out_filename)
                
                self.report_progress(0.92, "正在写入分类结果磁盘文件...")
                self.log_message('info', f'正在写入本地文件: {out_path}')
                df_output.to_excel(out_path, index=False)
                
            self.report_progress(0.98, "正在更新界面预览数据...")
            
            results = []
            for idx, text in enumerate(new_texts):
                r_item = {
                    '文案内容': str(text),
                    '分配编号': "N/A",
                    '匹配状态': "AI已分类",
                    '相似度': "-",
                    '最相似文案': "-",
                    'AI分类': ai_classifications[idx]
                }
                if translate_mode and translate_mode != "none":
                    r_item['翻译英文'] = translated_texts[idx]
                else:
                    r_item['翻译英文'] = ""
                results.append(r_item)
                
            js_cmd = f"window.showResults({json.dumps(results[:200], ensure_ascii=False)}, 0, {total_count}, {json.dumps(out_path.replace('\\', '/'), ensure_ascii=False)});"
            self._window.evaluate_js(js_cmd)
            self.log_message('success', '分类流程运行圆满完成！已更新前端显示。')
            
        except Exception as e:
            self.log_message('error', f'运行发生致命错误: {str(e)}')
            self._window.evaluate_js(f"window.showError({json.dumps(str(e), ensure_ascii=False)});")

    def test_ai_connection(self, api_key, model_name, ai_platform="google-ai-studio", ai_base_url="", ai_proxy=""):
        """
        异步运行 AI 接口连通性测试
        """
        threading.Thread(
            target=self._test_ai_connection_worker,
            args=(api_key, model_name, ai_platform, ai_base_url, ai_proxy),
            daemon=True
        ).start()
        return {"status": "started"}

    def _test_ai_connection_worker(self, api_key, model_name, ai_platform, ai_base_url, ai_proxy):
        try:
            self.log_message('system', '--- 开始 AI 接口连通性测试 ---')
            
            # Setup proxies
            proxies = None
            if ai_proxy and ai_proxy.strip():
                p_val = ai_proxy.strip()
                proxies = {"http": p_val, "https": p_val}
                self.log_message('info', f'[测试] 使用手动配置代理: {p_val}')
            else:
                import urllib.request
                detected = urllib.request.getproxies()
                if detected:
                    proxies = detected
                    self.log_message('info', f'[测试] 自动检测到系统代理: {proxies}')
                else:
                    self.log_message('info', '[测试] 未检测到代理，将尝试直接连接。')

            # Parse URL
            if not ai_base_url:
                if ai_platform == "vertex-ai":
                    base_url = "https://aiplatform.googleapis.com"
                else:
                    base_url = "https://generativelanguage.googleapis.com"
            else:
                base_url = ai_base_url.rstrip('/')

            if ai_platform == "vertex-ai":
                url = f"{base_url}/v1/publishers/google/models/{model_name}:generateContent?key={api_key}"
            else:
                url = f"{base_url}/v1beta/models/{model_name}:generateContent?key={api_key}"

            masked_url = f"{base_url}/v1beta/models/{model_name}:generateContent?key=***" if ai_platform != "vertex-ai" else f"{base_url}/v1/publishers/google/models/{model_name}:generateContent?key=***"
            self.log_message('info', f'[测试] 请求端点: {masked_url}')
            self.log_message('info', f'[测试] 目标模型: {model_name}')

            headers = {"Content-Type": "application/json"}
            payload = {
                "contents": [{
                    "role": "user",
                    "parts": [{
                        "text": "Hello, write a 3 word reply."
                    }]
                }]
            }

            self.log_message('info', '[测试] 正在发送 HTTP POST 请求...')
            response = requests.post(url, headers=headers, json=payload, proxies=proxies, timeout=15)
            
            self.log_message('info', f'[测试] 响应状态码: {response.status_code}')
            
            if response.status_code == 200:
                resp_data = response.json()
                try:
                    text_out = resp_data['candidates'][0]['content']['parts'][0]['text'].strip()
                    self.log_message('success', f'[测试] 连接成功！AI 响应内容: "{text_out}"')
                except Exception as parse_err:
                    self.log_message('warning', f'[测试] 请求成功，但返回的 JSON 结构意外: {response.text}')
            else:
                try:
                    err_json = response.json()
                    err_msg = err_json.get("error", {}).get("message", response.text)
                except Exception:
                    err_msg = response.text
                
                self.log_message('error', f'[测试] 连接失败 (HTTP {response.status_code}):\n{err_msg}')
                
        except Exception as e:
            self.log_message('error', f'[测试] 测试过程发生异常: {str(e)}')
        finally:
            self.log_message('system', '--- AI 接口连通性测试结束 ---')

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
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

if __name__ == "__main__":
    api = Api()
    
    html_path = get_resource_path(os.path.join('web', 'index.html'))
    
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
    
    icon_path = get_resource_path('app_icon.ico')
    if os.path.exists(icon_path):
        webview.start(icon=icon_path, debug=True)
    else:
        webview.start(debug=True)
