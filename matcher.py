import os
import re
import numpy as np
import pandas as pd
from datetime import datetime
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

class CopywritingMatcher:
    def __init__(self, inventory_path, id_prefix="CPY_", threshold=0.8, mode="tfidf",
                 use_google_sheets=False, google_sheets_url="", google_sheet_name="", google_creds_path=""):
        """
        初始化文案匹配器
        :param inventory_path: 库存 Excel 或 CSV 文件路径
        :param id_prefix: 分配编号的前缀，如 CPY_
        :param threshold: 相似度阈值 (0.0 - 1.0)
        :param mode: 匹配模式，'tfidf' (字面查重) 或 'semantic' (AI 语义查重)
        """
        self.inventory_path = inventory_path
        self.id_prefix = id_prefix
        self.threshold = threshold
        self.mode = mode.lower()
        
        self.use_google_sheets = use_google_sheets
        self.google_sheets_url = google_sheets_url
        self.google_sheet_name = google_sheet_name
        self.google_creds_path = google_creds_path
        
        self.df_inventory = None
        self.model = None  # AI 语义模型，延迟加载
        self.gc = None
        self.sh = None
        self.worksheet = None
        
        self.load_inventory()

    def load_inventory(self):
        """
        加载文案库存，如果不存在则自动创建模板，但不会因为读取错误轻易覆盖文件
        """
        if self.use_google_sheets:
            self.load_google_inventory()
            return

        if os.path.exists(self.inventory_path):
            try:
                # 根据后缀加载
                if self.inventory_path.endswith('.csv'):
                    self.df_inventory = pd.read_csv(self.inventory_path)
                else:
                    self.df_inventory = pd.read_excel(self.inventory_path)
                
                # 如果文件是空的（没有任何列或行），设置为 None，后续用输入文件格式初始化
                if len(self.df_inventory.columns) == 0:
                    self.df_inventory = None
            except Exception as e:
                # 打印错误，但不自动覆盖原文件，防止数据丢失
                print(f"加载库存文件失败: {e}。为了防止数据丢失，未重置该文件。")
                self.df_inventory = None
        else:
            self.create_empty_inventory()

    def load_google_inventory(self):
        """
        从 Google Sheets 加载网络文案库，如果工作表是空的，则进行初始化
        """
        try:
            from google.oauth2.service_account import Credentials
            import gspread
            
            scopes = [
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive'
            ]
            credentials = Credentials.from_service_account_file(self.google_creds_path, scopes=scopes)
            self.gc = gspread.authorize(credentials)
            self.sh = self.gc.open_by_url(self.google_sheets_url)
            
            if self.google_sheet_name:
                self.worksheet = self.sh.worksheet(self.google_sheet_name)
            else:
                self.worksheet = self.sh.get_worksheet(0)
                
            data = self.worksheet.get_all_values()
            if not data or len(data) == 0:
                # 空表，创建初始结构
                self.df_inventory = pd.DataFrame(columns=['编号', '文案内容', '入库时间', '匹配次数'])
                # 写入表头
                self.worksheet.update([['编号', '文案内容', '入库时间', '匹配次数']], 'A1')
            else:
                headers = data[0]
                rows = data[1:]
                self.df_inventory = pd.DataFrame(rows, columns=headers)
                
            if len(self.df_inventory.columns) == 0:
                self.df_inventory = None
        except Exception as e:
            print(f"加载谷歌表格库存失败: {e}")
            raise RuntimeError(f"加载谷歌表格库存失败: {e}。请检查您的 Google Sheet URL、凭证文件路径以及是否已向服务账号授权！")

    def create_empty_inventory(self):
        """
        创建一个空白的默认库存文件
        """
        self.df_inventory = pd.DataFrame(columns=['编号', '文案内容', '入库时间', '匹配次数'])
        self.save_inventory()

    def find_id_column(self, columns):
        """
        在给定的列名列表中寻找系统匹配编号列名（排除用户的贴文ID/ID列，以免覆盖）
        """
        candidates = ['分配编号', '编号']
        for cand in candidates:
            for col in columns:
                if str(col).strip().lower() == cand.lower():
                    return col
        for col in columns:
            if '分配编号' in str(col) or str(col) == '编号':
                return col
        return None

    def find_text_column(self, columns, target_col=None):
        """
        在给定的列名列表中寻找文案内容列名
        """
        if target_col and target_col in columns:
            return target_col
            
        candidates = ['外语文案', '中文文案', '文案内容', '文案', '最终文案', 'text', 'content']
        for cand in candidates:
            for col in columns:
                if str(col).strip().lower() == cand.lower():
                    return col
        for col in columns:
            if '文案' in str(col) or 'text' in str(col).lower() or 'content' in str(col).lower():
                return col
        # 排除常见非文本列，取剩下的第一个
        exclude_keywords = ['id', '编号', '链接', 'url', 'link', '时间', 'time', '次数', 'count']
        for col in columns:
            if not any(kw in str(col).lower() for kw in exclude_keywords):
                return col
        return columns[0] if columns else None

    def init_inventory_from_input(self, df_input, target_col):
        """
        根据输入文件和目标列初始化库存的列结构，保留原本的所有列并增加必需列
        """
        cols = list(df_input.columns)
        
        # 寻找或添加系统匹配编号列
        id_col = self.find_id_column(cols)
        if not id_col:
            cols.append('编号')
            id_col = '编号'
            
        # 确保有入库时间和匹配次数
        if '入库时间' not in cols:
            cols.append('入库时间')
        if '匹配次数' not in cols:
            cols.append('匹配次数')
            
        self.df_inventory = pd.DataFrame(columns=cols)

    def save_inventory(self):
        """
        保存当前的文案库存到本地文件或 Google Sheets
        """
        if self.df_inventory is None:
            return
            
        if self.use_google_sheets:
            try:
                # 填充空值并转换为字符串，确保在 gspread 中正常保存
                df_to_save = self.df_inventory.fillna("").astype(str)
                values = [df_to_save.columns.tolist()] + df_to_save.values.tolist()
                
                # 清除当前工作表，并全部重写以保持完全同步
                self.worksheet.clear()
                self.worksheet.update(values, 'A1')
            except Exception as e:
                print(f"保存谷歌表格库存失败: {e}")
                raise RuntimeError(f"保存谷歌表格库存失败: {e}")
        else:
            dir_name = os.path.dirname(self.inventory_path)
            if dir_name and not os.path.exists(dir_name):
                os.makedirs(dir_name)
            
            if self.inventory_path.endswith('.csv'):
                self.df_inventory.to_csv(self.inventory_path, index=False, encoding='utf-8-sig')
            else:
                self.df_inventory.to_excel(self.inventory_path, index=False)

    def clean_text(self, text):
        """
        清洗文本，统一小写，去除多余空白字符。支持浮点/空值处理。
        """
        if pd.isna(text) or text is None:
            return ""
        text_str = str(text).strip().lower()
        if text_str == 'nan':
            return ""
        text_str = re.sub(r'\s+', ' ', text_str)
        return text_str

    def get_next_id(self, current_max_id_str):
        """
        根据当前最大 ID 生成下一个递增 of ID，自动保持前导零的长度
        """
        match = re.search(r'\d+', current_max_id_str)
        if match:
            num = int(match.group())
            new_num = num + 1
            width = len(match.group())
            return f"{self.id_prefix}{str(new_num).zfill(width)}"
        else:
            # 如果没有提取到数字，从库存中扫描所有 ID 的最大值
            if self.df_inventory is not None:
                inv_cols = list(self.df_inventory.columns)
                id_col = self.find_id_column(inv_cols) or '编号'
                all_ids = self.df_inventory[id_col].tolist() if id_col in self.df_inventory.columns else []
            else:
                all_ids = []
            max_num = 0
            width = 6  # 默认 6 位前导零
            for idx in all_ids:
                m = re.search(r'\d+', str(idx))
                if m:
                    num = int(m.group())
                    if num > max_num:
                        max_num = num
                        width = len(m.group())
            new_num = max_num + 1
            return f"{self.id_prefix}{str(new_num).zfill(width)}"

    def fallback_similarity(self, text1, text2):
        """
        备用相似度计算：字符级别的 3-gram Jaccard 相似度
        在数据量极少或 TF-IDF 无法拟合时使用
        """
        if not text1 or not text2:
            return 0.0
        seq1 = set([text1[i:i+3] for i in range(len(text1)-2)])
        seq2 = set([text2[i:i+3] for i in range(len(text2)-2)])
        if not seq1 or not seq2:
            seq1 = set(text1)
            seq2 = set(text2)
        intersection = seq1.intersection(seq2)
        union = seq1.union(seq2)
        return len(intersection) / len(union) if union else 0.0

    def init_semantic_model(self, progress_callback=None):
        """
        初始化 AI 语义向量模型 (延迟加载，避免启动程序卡顿)
        """
        if self.mode == "semantic" and self.model is None:
            if progress_callback:
                progress_callback(0, 1, "正在初始化本地 AI 语义比对引擎，请稍候...")
            try:
                from sentence_transformers import SentenceTransformer
                self.model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
            except ImportError:
                raise ImportError("未检测到 AI 语义比对所需的底层依赖库 (sentence-transformers 或 PyTorch)。请先在系统设置中完成安装！")
            except Exception as e:
                raise RuntimeError(f"AI 语义模型加载失败: {e}")

    def process_batch(self, df_input, target_col='文案内容', progress_callback=None):
        """
        批量处理新文案的比对，并分配编号入库
        df_input: 输入的文案 DataFrame 或字符串列表
        target_col: 需要进行比对的外语/中文原文字段名称
        """
        # 兼容性处理：如果传入的是列表，转换为 DataFrame
        if not isinstance(df_input, pd.DataFrame):
            if isinstance(df_input, (list, tuple)) and df_input and isinstance(df_input[0], str):
                df_input = pd.DataFrame({target_col: df_input})
            else:
                df_input = pd.DataFrame(df_input)

        # 1. 如果库存为空或没有行，使用输入文件格式初始化
        if self.df_inventory is None or len(self.df_inventory) == 0:
            self.init_inventory_from_input(df_input, target_col)

        # 2. 识别库存中的 ID 列 and Text 列
        inv_cols = list(self.df_inventory.columns)
        id_col = self.find_id_column(inv_cols)
        if not id_col:
            id_col = '编号'
            self.df_inventory[id_col] = ""
            inv_cols = list(self.df_inventory.columns)

        text_col = self.find_text_column(inv_cols, target_col)
        if not text_col:
            text_col = target_col
            self.df_inventory.insert(1, text_col, "")
            inv_cols = list(self.df_inventory.columns)

        # 确保有时间与次数列
        if '入库时间' not in inv_cols:
            self.df_inventory['入库时间'] = ""
        if '匹配次数' not in inv_cols:
            self.df_inventory['匹配次数'] = ""

        # 确保结果相关的所有列在库存结构中存在
        inventory_result_cols = ['翻译英文', 'AI分类', '匹配状态', '相似度', '最相似文案']
        for col in inventory_result_cols:
            if col not in self.df_inventory.columns:
                self.df_inventory[col] = ""

        # 将 df_input 中存在但库存中没有的列动态增加到库存列结构中
        for col in df_input.columns:
            if col not in self.df_inventory.columns and col not in ['匹配状态', '相似度', '最相似文案']:
                self.df_inventory[col] = ""

        # 清洗/规整库存数据格式
        self.df_inventory[id_col] = self.df_inventory[id_col].fillna("").astype(str)
        self.df_inventory[text_col] = self.df_inventory[text_col].fillna("").astype(str)
        self.df_inventory['匹配次数'] = pd.to_numeric(self.df_inventory['匹配次数'], errors='coerce').fillna(1).astype(int)
        self.df_inventory['入库时间'] = self.df_inventory['入库时间'].replace("", np.nan).fillna(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

        # 如果是语义比对模式，先初始化模型
        if self.mode == "semantic":
            self.init_semantic_model(progress_callback)

        results = []
        
        # 3. 准备内存中的已存库文案列表
        inventory_texts = self.df_inventory[text_col].tolist()
        inventory_ids = self.df_inventory[id_col].tolist()
        inventory_clean = [self.clean_text(t) for t in inventory_texts]
        
        # 建立完全匹配的快速映射 (clean_text -> ID)
        clean_text_to_id = {}
        for clean_t, idx in zip(inventory_clean, inventory_ids):
            if clean_t and idx and idx != "nan":
                clean_text_to_id[clean_t] = idx

        # 获取当前的最大 ID
        current_max_id = ""
        valid_ids = [idx for idx in inventory_ids if idx and idx != "nan" and idx.strip()]
        if valid_ids:
            max_num = -1
            max_id_str = ""
            for idx in valid_ids:
                m = re.search(r'\d+', idx)
                if m:
                    num = int(m.group())
                    if num > max_num:
                        max_num = num
                        max_id_str = idx
            current_max_id = max_id_str if max_id_str else (self.id_prefix + "000000")
        else:
            current_max_id = self.id_prefix + "000000"

        # 4. 清洗新文本
        new_texts = df_input[target_col].tolist()
        cleaned_new_texts = [self.clean_text(t) for t in new_texts]
        
        # 维护一个在处理过程中动态增长的临时库存
        active_clean_texts = list(inventory_clean)
        active_ids = list(inventory_ids)
        active_original_texts = list(inventory_texts)
        
        # 记录原始数据库中各文本对应的 df_inventory 索引，方便更新“匹配次数”
        text_to_df_index = {t: i for i, t in enumerate(inventory_texts)}
        
        # 本次批处理中新产生的库存数据，处理结束后一次性合并
        inventory_updates_to_make = []
        total = len(new_texts)

        # 5. 根据模式预加载或计算表示矩阵
        use_tfidf = False
        vectorizer = None
        tfidf_matrix_active = None
        semantic_embeddings_active = None

        if self.mode == "tfidf":
            all_corpus = []
            for t in (active_original_texts + new_texts):
                if pd.isna(t) or t is None:
                    continue
                t_str = str(t).strip()
                if t_str and t_str.lower() != 'nan':
                    all_corpus.append(t_str)
            
            use_tfidf = len(all_corpus) >= 3
            if use_tfidf:
                try:
                    vectorizer = TfidfVectorizer(
                        analyzer='char_wb', 
                        ngram_range=(2, 5), 
                        min_df=1, 
                        token_pattern=None
                    )
                    vectorizer.fit(all_corpus)
                    if active_original_texts:
                        valid_active_texts = [t for t in active_original_texts if t and str(t).strip() and str(t).lower() != 'nan']
                        if valid_active_texts:
                            tfidf_matrix_active = vectorizer.transform(active_original_texts)
                except Exception as e:
                    print(f"TF-IDF 初始化失败: {e}，将降级为字符 Jaccard 算法。")
                    use_tfidf = False
        
        elif self.mode == "semantic":
            if progress_callback:
                progress_callback(0, total, "正在计算库存文案的语义特征空间向量...")
            
            if active_original_texts:
                try:
                    # 过滤可能存在的空字符串，保留列表长度对齐
                    semantic_embeddings_active = self.model.encode(
                        [t if t else "" for t in active_clean_texts], 
                        normalize_embeddings=True, 
                        show_progress_bar=False
                    )
                except Exception as e:
                    raise RuntimeError(f"库中文案 AI 语义编码失败: {e}")

        # 6. 循环处理每一条新文案
        for i, (orig_text, clean_new) in enumerate(zip(new_texts, cleaned_new_texts)):
            if progress_callback:
                progress_callback(i, total, f"正在进行相似度比对 ({i+1}/{total})...")
            
            # 过滤/忽略空白行（支持 None, NaN, "nan", 空白字符串）
            if not clean_new or not orig_text or not str(orig_text).strip() or pd.isna(orig_text):
                results.append({
                    '文案内容': "",
                    '分配编号': "N/A",
                    '匹配状态': "空文本",
                    '相似度': "0.0%",
                    '最相似文案': "",
                    '入库时间': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    '翻译英文': "",
                    'AI分类': ""
                })
                continue
                
            orig_text_str = str(orig_text)
            assigned_id = ""
            match_status = ""
            similarity = "0.0%"
            most_similar_text = ""
            stock_in_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            matched_trans = ""
            matched_ai_class = ""
            current_match_count = 1

            # A. 快速匹配：是否在当前库存中有完全一样的文案
            if clean_new in clean_text_to_id:
                matched_id = clean_text_to_id[clean_new]
                matched_idx = active_ids.index(matched_id)
                matched_orig = active_original_texts[matched_idx]
                
                assigned_id = matched_id
                match_status = "已存在 (完全匹配)"
                similarity = "100.0%"
                most_similar_text = matched_orig
                
                # 增加匹配次数，并获取已有翻译和分类
                if matched_orig in text_to_df_index:
                    df_idx = text_to_df_index[matched_orig]
                    self.df_inventory.at[df_idx, '匹配次数'] += 1
                    current_match_count = int(self.df_inventory.at[df_idx, '匹配次数'])
                    stock_in_time = str(self.df_inventory.at[df_idx, '入库时间'])
                    if '翻译英文' in self.df_inventory.columns:
                        val = str(self.df_inventory.at[df_idx, '翻译英文']).strip()
                        matched_trans = val if val.lower() != 'nan' else ""
                    if 'AI分类' in self.df_inventory.columns:
                        val = str(self.df_inventory.at[df_idx, 'AI分类']).strip()
                        matched_ai_class = val if val.lower() != 'nan' else ""
                else:
                    for item in inventory_updates_to_make:
                        if item[id_col] == matched_id:
                            item['匹配次数'] += 1
                            current_match_count = item['匹配次数']
                            if '入库时间' in item:
                                stock_in_time = item['入库时间']
                            if '翻译英文' in item:
                                matched_trans = str(item['翻译英文']).strip()
                            if 'AI分类' in item:
                                matched_ai_class = str(item['AI分类']).strip()
                            break

            else:
                # B. 模糊相似度比对
                max_sim = 0.0
                best_idx = -1
                
                # 过滤出有实际内容的 active_original_texts 的索引，避免匹配到库中的空行
                valid_active_indices = [idx for idx, t in enumerate(active_original_texts) if t and str(t).strip() and str(t).lower() != 'nan']
                
                if len(valid_active_indices) > 0:
                    if self.mode == "tfidf":
                        if use_tfidf and vectorizer is not None:
                            vec_new = vectorizer.transform([orig_text_str])
                            if tfidf_matrix_active is not None and tfidf_matrix_active.shape[0] > 0:
                                sims = cosine_similarity(vec_new, tfidf_matrix_active)[0]
                                best_idx = valid_active_indices[0]
                                max_sim = sims[best_idx]
                                for idx_inv in valid_active_indices:
                                    if sims[idx_inv] > max_sim:
                                        max_sim = sims[idx_inv]
                                        best_idx = idx_inv
                        else:
                            for idx_inv in valid_active_indices:
                                sim = self.fallback_similarity(clean_new, active_clean_texts[idx_inv])
                                if sim > max_sim:
                                    max_sim = sim
                                    best_idx = idx_inv
                    elif self.mode == "semantic":
                        vec_new = self.model.encode([clean_new], normalize_embeddings=True, show_progress_bar=False)
                        if semantic_embeddings_active is not None and len(semantic_embeddings_active) > 0:
                            sims = cosine_similarity(vec_new, semantic_embeddings_active)[0]
                            best_idx = valid_active_indices[0]
                            max_sim = sims[best_idx]
                            for idx_inv in valid_active_indices:
                                if sims[idx_inv] > max_sim:
                                    max_sim = sims[idx_inv]
                                    best_idx = idx_inv
                
                # C. 相似度阈值处理
                if max_sim >= self.threshold:
                    matched_orig = active_original_texts[best_idx]
                    matched_id = active_ids[best_idx]
                    
                    assigned_id = matched_id
                    match_status = "已存在 (模糊匹配)" if self.mode == "tfidf" else "已存在 (AI语义匹配)"
                    similarity = f"{max_sim * 100:.1f}%"
                    most_similar_text = matched_orig
                    
                    # 增加匹配次数，并获取已有翻译和分类
                    if matched_orig in text_to_df_index:
                        df_idx = text_to_df_index[matched_orig]
                        self.df_inventory.at[df_idx, '匹配次数'] += 1
                        current_match_count = int(self.df_inventory.at[df_idx, '匹配次数'])
                        stock_in_time = str(self.df_inventory.at[df_idx, '入库时间'])
                        if '翻译英文' in self.df_inventory.columns:
                            val = str(self.df_inventory.at[df_idx, '翻译英文']).strip()
                            matched_trans = val if val.lower() != 'nan' else ""
                        if 'AI分类' in self.df_inventory.columns:
                            val = str(self.df_inventory.at[df_idx, 'AI分类']).strip()
                            matched_ai_class = val if val.lower() != 'nan' else ""
                    else:
                        for item in inventory_updates_to_make:
                            if item[id_col] == matched_id:
                                item['匹配次数'] += 1
                                current_match_count = item['匹配次数']
                                if '入库时间' in item:
                                    stock_in_time = item['入库时间']
                                if '翻译英文' in item:
                                    matched_trans = str(item['翻译英文']).strip()
                                if 'AI分类' in item:
                                    matched_ai_class = str(item['AI分类']).strip()
                                break
                    
                    # 记录快速查重映射
                    clean_text_to_id[clean_new] = matched_id
                else:
                    # D. 匹配不成功，分配新 ID 并动态追加至比对集合中
                    new_id = self.get_next_id(current_max_id)
                    current_max_id = new_id
                    
                    assigned_id = new_id
                    match_status = "新文案"
                    similarity = "0.0%"
                    most_similar_text = ""
                    
                    active_original_texts.append(orig_text_str)
                    active_clean_texts.append(clean_new)
                    active_ids.append(new_id)
                    clean_text_to_id[clean_new] = new_id
                    
                    # 动态追加新的比对向量
                    if self.mode == "tfidf":
                        if use_tfidf and vectorizer is not None:
                            vec_new = vectorizer.transform([orig_text_str])
                            import scipy.sparse as sp
                            if tfidf_matrix_active is not None:
                                tfidf_matrix_active = sp.vstack([tfidf_matrix_active, vec_new])
                            else:
                                tfidf_matrix_active = vec_new
                    elif self.mode == "semantic":
                        vec_new = self.model.encode([clean_new], normalize_embeddings=True, show_progress_bar=False)
                        if semantic_embeddings_active is not None and len(semantic_embeddings_active) > 0:
                            semantic_embeddings_active = np.vstack([semantic_embeddings_active, vec_new])
                        else:
                            semantic_embeddings_active = vec_new
            
            # E. 构造并记录需要写入库存的行（不论是新文案，还是已存在匹配文案，均写入库存）
            input_row = df_input.iloc[i]
            new_item = {}
            for col in self.df_inventory.columns:
                if col == id_col:
                    new_item[id_col] = assigned_id
                elif col == '入库时间':
                    new_item['入库时间'] = stock_in_time
                elif col == '匹配次数':
                    new_item['匹配次数'] = current_match_count
                elif col == '翻译英文':
                    new_item['翻译英文'] = matched_trans
                elif col == 'AI分类':
                    new_item['AI分类'] = matched_ai_class
                elif col == '匹配状态':
                    new_item['匹配状态'] = match_status
                elif col == '相似度':
                    new_item['相似度'] = similarity
                elif col == '最相似文案':
                    new_item['最相似文案'] = most_similar_text
                else:
                    if col in input_row:
                        val = input_row[col]
                        if pd.isna(val):
                            val = ""
                        new_item[col] = val
                    else:
                        new_item[col] = ""
            
            inventory_updates_to_make.append(new_item)
            
            results.append({
                '文案内容': orig_text_str,
                '分配编号': assigned_id,
                '匹配状态': match_status,
                '相似度': similarity,
                '最相似文案': most_similar_text,
                '入库时间': stock_in_time,
                '翻译英文': matched_trans,
                'AI分类': matched_ai_class
            })
            
        # E. 保存并合并新增库存
        if inventory_updates_to_make:
            df_new_items = pd.DataFrame(inventory_updates_to_make)
            self.df_inventory = pd.concat([self.df_inventory, df_new_items], ignore_index=True)
        
        self.save_inventory()
        
        if progress_callback:
            progress_callback(total, total, "处理完成，库存已更新！")
            
        return results
