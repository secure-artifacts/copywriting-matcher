/* -------------------------------------------------------------
 * 爆贴文案查重与库存管理系统 - 前端交互逻辑 JS
 * ------------------------------------------------------------- */

let selectedInputPath = "";
let libraryType = 'local';
let inputType = 'local';
let savedWriteColumn = 'NEW_COL';

// 全局配置状态对象
let currentSettings = {
    theme: 'dark',
    bgImage: '',
    blur: 10,
    opacity: 75,
    inventoryPath: '',
    prefix: 'CPY_',
    mode: 'tfidf',
    threshold: 80,
    libraryType: 'local',
    googleSheetUrl: '',
    googleSheetName: '',
    googleCredsPath: '',
    writeColumn: 'NEW_COL',
    inputType: 'local',
    googleInputUrl: '',
    googleInputName: '',
    aiClassifyEnable: false,
    aiApiKey: '',
    aiModel: 'gemini-3.1-flash-lite',
    aiBatchSize: 100,
    aiConcurrency: 3,
    aiColName: 'AI分类',
    aiRules: '',
    translateMode: 'none'
};

// 保存当前设置到后端
function saveCurrentSettings() {
    if (!window.pywebview) return;
    
    currentSettings.theme = document.body.className.replace('theme-', '') || 'dark';
    
    const bgElem = document.getElementById('app-bg');
    let bgUrlVal = bgElem.style.getPropertyValue('--bg-image-url') || '';
    if (bgUrlVal.startsWith("url('") && bgUrlVal.endsWith("')")) {
        currentSettings.bgImage = bgUrlVal.slice(5, -2);
    } else if (bgUrlVal.startsWith('url("') && bgUrlVal.endsWith('")')) {
        currentSettings.bgImage = bgUrlVal.slice(5, -2);
    } else {
        currentSettings.bgImage = (bgUrlVal === 'none' || !bgUrlVal) ? '' : bgUrlVal;
    }
    
    currentSettings.blur = parseInt(document.getElementById('blur-slider').value) || 0;
    currentSettings.opacity = parseInt(document.getElementById('opacity-slider').value) || 75;
    
    currentSettings.inventoryPath = document.getElementById('inventory-path').value.trim();
    currentSettings.prefix = document.getElementById('prefix-input').value.trim();
    currentSettings.mode = document.getElementById('mode-select').value;
    currentSettings.threshold = parseInt(document.getElementById('threshold-slider').value) || 80;

    // 新增网络库与写入列设置
    currentSettings.libraryType = libraryType;
    currentSettings.googleSheetUrl = document.getElementById('google-sheet-url').value.trim();
    currentSettings.googleSheetName = document.getElementById('google-sheet-name-select').value;
    currentSettings.googleCredsPath = document.getElementById('google-creds-path').value.trim();
    currentSettings.writeColumn = document.getElementById('column-write-select').value;
    
    // 新增待比对表格设置
    currentSettings.inputType = inputType;
    currentSettings.googleInputUrl = document.getElementById('google-input-url').value.trim();
    currentSettings.googleInputName = document.getElementById('google-input-name-select').value;

    // 新增 AI 分类设置
    currentSettings.aiClassifyEnable = document.getElementById('ai-classify-enable').checked;
    currentSettings.aiApiKey = document.getElementById('ai-api-key').value.trim();
    currentSettings.aiPlatform = document.getElementById('ai-platform').value;
    currentSettings.aiBaseUrl = "";
    currentSettings.aiModel = document.getElementById('ai-model').value;
    currentSettings.aiCustomModel = "";
    currentSettings.aiProxy = "";
    currentSettings.aiColumnSelect = document.getElementById('ai-column-select').value;
    currentSettings.aiBatchSize = parseInt(document.getElementById('ai-batch-size').value) || 100;
    currentSettings.aiConcurrency = parseInt(document.getElementById('ai-concurrency').value) || 3;
    currentSettings.aiColName = document.getElementById('ai-col-name').value.trim() || 'AI分类';
    currentSettings.aiRules = document.getElementById('ai-rules').value;
    
    // 新增翻译配置
    currentSettings.translateMode = document.getElementById('translate-mode').value;
    currentSettings.translateModel = document.getElementById('translate-model').value;

    window.pywebview.api.save_settings(JSON.stringify(currentSettings));
}

// 加载设置并应用
function loadSavedSettings() {
    if (!window.pywebview) return;
    
    window.pywebview.api.load_settings().then(function(settings) {
        if (settings) {
            // 恢复主题
            if (settings.theme) {
                setTheme(settings.theme, true);
            } else {
                setTheme('dark', true);
            }
            
            // 恢复自定义背景
            if (settings.bgImage) {
                document.getElementById('app-bg').style.setProperty('--bg-image-url', `url('${settings.bgImage}')`);
            } else {
                document.getElementById('app-bg').style.setProperty('--bg-image-url', 'none');
            }
            
            // 恢复模糊度
            if (settings.blur !== undefined) {
                const blurVal = parseInt(settings.blur);
                document.getElementById('blur-slider').value = blurVal;
                onBlurChange(blurVal);
            }
            
            // 恢复不透明度
            if (settings.opacity !== undefined) {
                const opacityVal = parseInt(settings.opacity);
                document.getElementById('opacity-slider').value = opacityVal;
                onOpacityChange(opacityVal);
            }
            
            // 恢复前缀
            if (settings.prefix !== undefined) {
                document.getElementById('prefix-input').value = settings.prefix;
            }
            
            // 恢复比对模式
            if (settings.mode !== undefined) {
                document.getElementById('mode-select').value = settings.mode;
                onModeChange(true);
            }
            
            // 恢复相似度阈值
            if (settings.threshold !== undefined) {
                const thresholdVal = parseInt(settings.threshold);
                document.getElementById('threshold-slider').value = thresholdVal;
                onThresholdChange(thresholdVal);
            }
            
            // 恢复数据库路径
            if (settings.inventoryPath) {
                document.getElementById('inventory-path').value = settings.inventoryPath;
            } else {
                window.pywebview.api.get_default_inventory_path().then(function(path) {
                    document.getElementById('inventory-path').value = path;
                });
            }

            // 恢复网络库与写入列设置
            if (settings.libraryType) {
                switchLibraryType(settings.libraryType, true);
            } else {
                switchLibraryType('local', true);
            }
            
            if (settings.googleSheetUrl !== undefined) {
                document.getElementById('google-sheet-url').value = settings.googleSheetUrl;
            }
            if (settings.googleSheetName !== undefined) {
                const select = document.getElementById('google-sheet-name-select');
                if (settings.googleSheetName) {
                    select.innerHTML = `<option value="${settings.googleSheetName}">${settings.googleSheetName}</option>`;
                    select.value = settings.googleSheetName;
                }
            }
            if (settings.googleCredsPath !== undefined) {
                document.getElementById('google-creds-path').value = settings.googleCredsPath;
            }
            if (settings.writeColumn !== undefined) {
                savedWriteColumn = settings.writeColumn;
            }

            // 恢复待比对表格的配置
            if (settings.inputType) {
                switchInputType(settings.inputType, true);
            } else {
                switchInputType('local', true);
            }
            if (settings.googleInputUrl !== undefined) {
                document.getElementById('google-input-url').value = settings.googleInputUrl;
            }
            if (settings.googleInputName !== undefined) {
                const select = document.getElementById('google-input-name-select');
                if (settings.googleInputName) {
                    select.innerHTML = `<option value="${settings.googleInputName}">${settings.googleInputName}</option>`;
                    select.value = settings.googleInputName;
                }
            }
            // 恢复 AI 智能分类配置
            if (settings.aiClassifyEnable !== undefined) {
                document.getElementById('ai-classify-enable').checked = settings.aiClassifyEnable;
                toggleAiClassifyEnabled();
            }
            if (settings.aiApiKey !== undefined) {
                document.getElementById('ai-api-key').value = settings.aiApiKey;
            }
            if (settings.aiPlatform !== undefined) {
                document.getElementById('ai-platform').value = settings.aiPlatform;
            }
            onAiPlatformChange();
            if (settings.aiModel !== undefined) {
                document.getElementById('ai-model').value = settings.aiModel;
            }
            onAiModelChange();
            if (settings.aiColumnSelect !== undefined) {
                document.getElementById('ai-column-select').value = settings.aiColumnSelect;
            }
            if (settings.aiBatchSize !== undefined) {
                document.getElementById('ai-batch-size').value = settings.aiBatchSize;
            } else {
                document.getElementById('ai-batch-size').value = 100;
            }
            if (settings.aiConcurrency !== undefined) {
                document.getElementById('ai-concurrency').value = settings.aiConcurrency;
            } else {
                document.getElementById('ai-concurrency').value = 3;
            }
            if (settings.aiColName !== undefined) {
                document.getElementById('ai-col-name').value = settings.aiColName;
            } else {
                document.getElementById('ai-col-name').value = "AI分类";
            }
            if (settings.aiRules !== undefined && settings.aiRules) {
                document.getElementById('ai-rules').value = settings.aiRules;
            } else {
                document.getElementById('ai-rules').value = DEFAULT_AI_RULES;
            }

            if (settings.translateMode !== undefined) {
                document.getElementById('translate-mode').value = settings.translateMode;
            } else {
                document.getElementById('translate-mode').value = 'none';
            }
            if (settings.translateModel !== undefined) {
                document.getElementById('translate-model').value = settings.translateModel;
            } else {
                document.getElementById('translate-model').value = 'gemini-2.5-flash';
            }

            // 自动静默加载待比对谷歌表格的子表与列头，激活被禁用的下拉框
            if (settings.inputType === 'google' && settings.googleInputUrl && settings.googleCredsPath) {
                setTimeout(() => {
                    verifyAndLoadInputSheets(true);
                }, 800);
            }
            // 自动静默加载库存库的工作表列表
            if (settings.libraryType === 'google' && settings.googleSheetUrl && settings.googleCredsPath) {
                setTimeout(() => {
                    verifyAndLoadInventorySheets(true);
                }, 800);
            }
        } else {
            window.pywebview.api.get_default_inventory_path().then(function(path) {
                document.getElementById('inventory-path').value = path;
            });
            document.getElementById('ai-rules').value = DEFAULT_AI_RULES;
        }
    });
}

function switchLibraryType(type, skipSave) {
    libraryType = type;
    const tabLocal = document.getElementById('tab-local-lib');
    const tabGoogle = document.getElementById('tab-google-lib');
    const localGroup = document.getElementById('local-library-group');
    const googleGroup = document.getElementById('google-library-group');
    
    if (type === 'local') {
        tabLocal.classList.add('active');
        tabGoogle.classList.remove('active');
        localGroup.style.display = 'block';
        googleGroup.style.display = 'none';
    } else {
        tabLocal.classList.remove('active');
        tabGoogle.classList.add('active');
        localGroup.style.display = 'none';
        googleGroup.style.display = 'block';
    }
    
    if (!skipSave) {
        saveCurrentSettings();
    }
}

function switchInputType(type, skipSave) {
    inputType = type;
    const tabLocal = document.getElementById('tab-local-input');
    const tabGoogle = document.getElementById('tab-google-input');
    const localGroup = document.getElementById('local-input-group');
    const googleGroup = document.getElementById('google-input-group');
    
    if (type === 'local') {
        tabLocal.classList.add('active');
        tabGoogle.classList.remove('active');
        localGroup.style.display = 'block';
        googleGroup.style.display = 'none';
    } else {
        tabLocal.classList.remove('active');
        tabGoogle.classList.add('active');
        localGroup.style.display = 'none';
        googleGroup.style.display = 'block';
    }
    
    if (!skipSave) {
        saveCurrentSettings();
    }
}

function pickGoogleCredsFile() {
    if (window.pywebview) {
        window.pywebview.api.select_credentials_file().then(function(path) {
            if (path) {
                document.getElementById('google-creds-path').value = path;
                saveCurrentSettings();
                
                // 自动刷新表格子表和列信息
                if (inputType === 'google') {
                    verifyAndLoadInputSheets(true);
                }
                if (libraryType === 'google') {
                    verifyAndLoadInventorySheets(true);
                }
            }
        });
    }
}

function verifyAndLoadInventorySheets(silent) {
    const url = document.getElementById('google-sheet-url').value.trim();
    const creds = document.getElementById('google-creds-path').value.trim();
    const btn = document.getElementById('btn-verify-inv-google');
    
    console.log("verifyAndLoadInventorySheets starting. URL:", url, "Creds:", creds, "Silent:", silent);
    
    if (!url) {
        if (!silent) alert("请输入库存谷歌表格链接！");
        return;
    }
    if (!creds) {
        if (!silent) alert("请先在上方选择谷歌服务账号凭证 JSON 文件！");
        return;
    }
    
    if (btn) {
        btn.disabled = true;
        btn.textContent = "⚡ 正在连接核验...";
    }
    
    window.pywebview.api.get_google_worksheets(url, creds).then(function(sheets) {
        console.log("verifyAndLoadInventorySheets worksheets API returned:", sheets);
        if (btn) btn.disabled = false;
        
        if (sheets && sheets.error) {
            if (btn) btn.textContent = "❌ 验证连接失败，请重试";
            if (!silent) alert("谷歌表格连接核验失败:\n" + sheets.error + "\n\n请确认：\n1. 表格链接是否正确。\n2. 凭证文件是否有效。\n3. 您是否已将服务账号邮箱添加为表格的共享协作者 (Editor)。");
            return;
        }
        
        if (Array.isArray(sheets)) {
            const select = document.getElementById('google-sheet-name-select');
            const savedVal = select.value || currentSettings.googleSheetName;
            select.innerHTML = "";
            sheets.forEach(name => {
                const opt = document.createElement('option');
                opt.value = name;
                opt.textContent = name;
                select.appendChild(opt);
            });
            
            if (sheets.includes(savedVal)) {
                select.value = savedVal;
            } else if (sheets.length > 0) {
                select.value = sheets[0];
            }
            
            if (btn) {
                btn.textContent = "✅ 连接成功，已载入工作表列表";
                btn.style.background = "rgba(16, 185, 129, 0.15)";
                btn.style.borderColor = "rgba(16, 185, 129, 0.3)";
            }
            saveCurrentSettings();
        } else {
            if (btn) btn.textContent = "❌ 验证连接失败，请重试";
            if (!silent) alert("谷歌表格连接返回了非预期的数据，请重试。");
        }
    }).catch(function(err) {
        console.error("verifyAndLoadInventorySheets worksheets API failed with catch:", err);
        if (btn) {
            btn.disabled = false;
            btn.textContent = "❌ 验证连接失败，请重试";
        }
        if (!silent) alert("发生连接错误，请检查网络或参数:\n" + err);
    });
}

function verifyAndLoadInputSheets(silent) {
    const url = document.getElementById('google-input-url').value.trim();
    const creds = document.getElementById('google-creds-path').value.trim();
    const btn = document.getElementById('btn-verify-input-google');
    
    console.log("verifyAndLoadInputSheets starting. URL:", url, "Creds:", creds, "Silent:", silent);
    
    if (!url) {
        if (!silent) alert("请输入待比对谷歌表格链接！");
        return;
    }
    if (!creds) {
        if (!silent) alert("请先在上方选择谷歌服务账号凭证 JSON 文件！");
        return;
    }
    
    if (btn) {
        btn.disabled = true;
        btn.textContent = "⚡ 正在连接核验...";
    }
    
    window.pywebview.api.get_google_worksheets(url, creds).then(function(sheets) {
        console.log("verifyAndLoadInputSheets worksheets API returned:", sheets);
        if (btn) btn.disabled = false;
        
        if (sheets && sheets.error) {
            if (btn) btn.textContent = "❌ 验证连接失败，请重试";
            if (!silent) alert("待比对表格连接核验失败:\n" + sheets.error + "\n\n请确认：\n1. 表格链接是否正确。\n2. 凭证文件是否有效。\n3. 您是否已将服务账号邮箱添加为表格的共享协作者 (Editor)。");
            return;
        }
        
        if (Array.isArray(sheets)) {
            const select = document.getElementById('google-input-name-select');
            const savedVal = select.value || currentSettings.googleInputName;
            select.innerHTML = "";
            sheets.forEach(name => {
                const opt = document.createElement('option');
                opt.value = name;
                opt.textContent = name;
                select.appendChild(opt);
            });
            
            if (sheets.includes(savedVal)) {
                select.value = savedVal;
            } else if (sheets.length > 0) {
                select.value = sheets[0];
            }
            
            if (btn) {
                btn.textContent = "✅ 连接成功，已载入工作表与列";
                btn.style.background = "rgba(16, 185, 129, 0.15)";
                btn.style.borderColor = "rgba(16, 185, 129, 0.3)";
            }
            
            // 加载列信息
            loadGoogleInputColumns(silent);
        } else {
            if (btn) btn.textContent = "❌ 验证连接失败，请重试";
            if (!silent) alert("谷歌表格连接返回了非预期的数据，请重试。");
        }
    }).catch(function(err) {
        console.error("verifyAndLoadInputSheets worksheets API failed with catch:", err);
        if (btn) {
            btn.disabled = false;
            btn.textContent = "❌ 验证连接失败，请重试";
        }
        if (!silent) alert("发生连接错误，请检查网络或参数:\n" + err);
    });
}

function loadGoogleInputColumns(silent) {
    const url = document.getElementById('google-input-url').value.trim();
    const name = document.getElementById('google-input-name-select').value;
    const creds = document.getElementById('google-creds-path').value.trim();
    
    console.log("loadGoogleInputColumns starting. URL:", url, "Worksheet:", name, "Creds:", creds, "Silent:", silent);
    
    if (url && creds) {
        updateStatusText("正在解析待比对表格列头名...");
        window.pywebview.api.get_google_columns(url, creds, name).then(function(cols) {
            console.log("loadGoogleInputColumns columns API returned:", cols);
            populateColumnsSelect(cols, true);
            saveCurrentSettings();
        }).catch(function(err) {
            console.error("loadGoogleInputColumns columns API failed with catch:", err);
            updateStatusText("❌ 载入网络表格列失败");
            if (!silent) alert("载入列名出错:\n" + err);
        });
    }
}

function populateColumnsSelect(cols, isGoogle) {
    console.log("populateColumnsSelect entering. columns:", cols, "isGoogle:", isGoogle);
    const colSelect = document.getElementById('column-select');
    colSelect.innerHTML = "";
    
    const colWriteSelect = document.getElementById('column-write-select');
    colWriteSelect.innerHTML = "";

    const aiColSelect = document.getElementById('ai-column-select');
    if (aiColSelect) {
        aiColSelect.innerHTML = "";
    }
    
    const defaultWriteOpt = document.createElement('option');
    defaultWriteOpt.value = "NEW_COL";
    defaultWriteOpt.textContent = "新建 '分配编号' 列";
    colWriteSelect.appendChild(defaultWriteOpt);
    
    if (cols && cols.error) {
        alert("解析表格表头失败:\n" + cols.error);
        updateStatusText(isGoogle ? "❌ 载入网络表格错误" : "❌ 载入文件错误");
        return;
    }
    
    if (Array.isArray(cols) && cols.length > 0) {
        cols.forEach(col => {
            const opt = document.createElement('option');
            opt.value = col;
            opt.textContent = col;
            colSelect.appendChild(opt);
            
            const optWrite = document.createElement('option');
            optWrite.value = col;
            optWrite.textContent = col;
            colWriteSelect.appendChild(optWrite);

            if (aiColSelect) {
                const optAi = document.createElement('option');
                optAi.value = col;
                optAi.textContent = col;
                aiColSelect.appendChild(optAi);
            }
        });
        colSelect.disabled = false;
        colWriteSelect.disabled = false;
        if (aiColSelect) {
            aiColSelect.disabled = false;
        }
        
        // 智能选择最匹配的文案列
        let defaultCol = cols[0];
        const keywords = ["文案", "内容", "文本", "text", "content", "copywriting"];
        for (let col of cols) {
            let colLower = String(col).toLowerCase();
            if (keywords.some(kw => colLower.includes(kw))) {
                defaultCol = col;
                break;
            }
        }
        colSelect.value = defaultCol;
        if (aiColSelect) {
            if (cols.includes(currentSettings.aiColumnSelect)) {
                aiColSelect.value = currentSettings.aiColumnSelect;
            } else {
                aiColSelect.value = defaultCol;
            }
        }
        
        // 智能选择编号写入列
        if (cols.includes(savedWriteColumn)) {
            colWriteSelect.value = savedWriteColumn;
        } else {
            colWriteSelect.value = "NEW_COL";
        }
        
        updateStatusText(isGoogle ? "✅ 谷歌表格载入成功，可以开始比对。" : "✅ 表格导入成功，点击下方按钮开始比对。");
    } else {
        const opt = document.createElement('option');
        opt.textContent = "第一列 (默认)";
        colSelect.appendChild(opt);
        colSelect.disabled = true;
        
        colWriteSelect.value = "NEW_COL";
        colWriteSelect.disabled = true;

        if (aiColSelect) {
            const optAi = document.createElement('option');
            optAi.textContent = "第一列 (默认)";
            aiColSelect.appendChild(optAi);
            aiColSelect.disabled = true;
        }
        updateStatusText(isGoogle ? "⚠️ 未能识别列名，默认使用第一列，且新建编号列。" : "⚠️ 未能识别列名，默认使用第一列，且新建编号列。");
    }
}

// 1. 初始化，等待 Python webviewready 事件
window.addEventListener('pywebviewready', function() {
    loadSavedSettings();
});

// 选择主库存数据库文件 (.xlsx / .csv)
function pickInventoryFile() {
    if (window.pywebview) {
        window.pywebview.api.select_file('inventory').then(function(path) {
            if (path) {
                document.getElementById('inventory-path').value = path;
                saveCurrentSettings();
            }
        });
    }
}

// 选择待处理新文件，并自动提取表头
function pickInputFile() {
    if (window.pywebview) {
        window.pywebview.api.select_file('input').then(function(path) {
            if (path) {
                selectedInputPath = path;
                document.getElementById('input-path').value = path;
                
                // 加载表头
                updateStatusText("正在解析表格列头名...");
                window.pywebview.api.get_columns(path).then(function(cols) {
                    populateColumnsSelect(cols, false);
                });
            }
        });
    }
}

// 滑动相似度滑块
function onThresholdChange(val) {
    document.getElementById('threshold-val').textContent = "相似度阈值: " + val + "%";
}

// 切换查重模式说明
function onModeChange(skipSave) {
    const mode = document.getElementById('mode-select').value;
    const bubble = document.getElementById('info-bubble');
    if (mode === 'tfidf') {
        bubble.innerHTML = "📖 字面查重说明:<br>1. 采用 TF-IDF 字符分析和余弦相似度算法。<br>2. 适合拼写极其相似的文案比对，速度极快。";
    } else {
        bubble.innerHTML = "📖 AI语义查重说明:<br>1. 采用开源多语言 AI 模型，可理解上下文语义。<br>2. 支持匹配同义词替换（如“别哭”和“别担心”）。<br>3. 首次启动将下载 420MB 语言模型，请耐心等候。";
    }
    if (!skipSave) {
        saveCurrentSettings();
    }
}

// ------------------ 皮肤/背景定制逻辑 ------------------

// 切换预设主题
function setTheme(themeName, skipSave) {
    // 移除旧主题 class
    document.body.className = "";
    document.body.classList.add("theme-" + themeName);
    
    // 更新主题圆点的 active 状态
    const dots = document.querySelectorAll('.theme-dot');
    dots.forEach(dot => dot.classList.remove('active'));
    
    const activeDot = document.querySelector('.theme-dot-' + themeName);
    if (activeDot) {
        activeDot.classList.add('active');
    }
    if (!skipSave) {
        saveCurrentSettings();
    }
}

// 触发背景图片上传点击
function triggerBgUpload() {
    document.getElementById('bg-uploader').click();
}

// 读取用户本地背景图片
function loadCustomBg(input) {
    if (input.files && input.files[0]) {
        const reader = new FileReader();
        reader.onload = function(e) {
            const dataUrl = e.target.result;
            // 实时应用到背景容器
            document.getElementById('app-bg').style.setProperty('--bg-image-url', `url('${dataUrl}')`);
            saveCurrentSettings();
        };
        reader.readAsDataURL(input.files[0]);
    }
}

// 还原为默认渐变色背景
function resetDefaultBg() {
    document.getElementById('app-bg').style.setProperty('--bg-image-url', 'none');
    document.getElementById('bg-uploader').value = ""; // 清空上传文件
    saveCurrentSettings();
}

// 背景模糊度调节
function onBlurChange(val) {
    document.getElementById('blur-val').textContent = "背景模糊度: " + val + "px";
    document.documentElement.style.setProperty('--blur-amount', val + "px");
}

// 卡片透明度调节
function onOpacityChange(val) {
    document.getElementById('opacity-val').textContent = "面板不透明度: " + val + "%";
    document.documentElement.style.setProperty('--card-opacity', (val / 100));
}

// ------------------ 算法处理与接口对接 ------------------

let outputFilePath = "";

// 开始匹配计算
function startProcessing() {
    const invPath = document.getElementById('inventory-path').value.trim();
    const inputPath = document.getElementById('input-path').value.trim();
    const colName = document.getElementById('column-select').value;
    const writeColName = document.getElementById('column-write-select').value;
    const prefix = document.getElementById('prefix-input').value.trim();
    const threshold = document.getElementById('threshold-slider').value / 100;
    const mode = document.getElementById('mode-select').value;

    const googleSheetUrl = document.getElementById('google-sheet-url').value.trim();
    const googleSheetName = document.getElementById('google-sheet-name-select').value;
    const googleCredsPath = document.getElementById('google-creds-path').value.trim();

    const googleInputUrl = document.getElementById('google-input-url').value.trim();
    const googleInputName = document.getElementById('google-input-name-select').value;

    const translateMode = document.getElementById('translate-mode').value;
    const translateModel = document.getElementById('translate-model').value;
    const aiApiKey = document.getElementById('ai-api-key').value.trim();
    const aiPlatform = document.getElementById('ai-platform').value;
    const aiModel = document.getElementById('ai-model').value;
    const aiRules = document.getElementById('ai-rules').value;
    const aiBatchSize = parseInt(document.getElementById('ai-batch-size').value) || 100;
    const aiConcurrency = parseInt(document.getElementById('ai-concurrency').value) || 3;
    const aiColName = document.getElementById('ai-col-name').value.trim() || 'AI分类';

    if (libraryType === 'local') {
        if (!invPath) {
            alert("请输入或选择本地库存文件路径！");
            return;
        }
    } else {
        if (!googleSheetUrl) {
            alert("请输入谷歌表格链接 (Google Sheets URL)！");
            return;
        }
        if (!googleCredsPath) {
            alert("请选择谷歌服务账号凭证 JSON 文件！");
            return;
        }
    }
    
    if (inputType === 'local') {
        if (!inputPath) {
            alert("请选择需要处理的新文案表格！");
            return;
        }
    } else {
        if (!googleInputUrl) {
            alert("请输入谷歌待比对表格链接 (Google Sheets URL)！");
            return;
        }
        if (!googleCredsPath) {
            alert("请选择谷歌服务账号凭证 JSON 文件！");
            return;
        }
    }
    
    if (!prefix) {
        alert("编号前缀不能为空！");
        return;
    }

    const aiClassifyEnable = document.getElementById('ai-classify-enable').checked;

    if (aiClassifyEnable && !aiApiKey) {
        alert("您启用了 AI 智能分类，请先在下方【🤖 AI 智能分类配置】中配置您的 API Key！");
        return;
    }

    if (translateMode !== 'none' && !aiApiKey) {
        alert("您启用了跨语言翻译，请先在下方【🤖 AI 智能分类配置】中配置您的 API Key！");
        return;
    }

    // 锁定界面组件
    setUiState(true);

    // 清空上次结果与状态
    document.getElementById('result-tbody').innerHTML = `
        <tr class="empty-placeholder">
            <td colspan="6">正在计算中，请耐心等候...</td>
        </tr>
    `;
    document.getElementById('stat-total').textContent = "0";
    document.getElementById('stat-matched').textContent = "0";
    document.getElementById('stat-new').textContent = "0";
    document.getElementById('output-filepath').textContent = "";
    document.getElementById('btn-open-folder').disabled = true;

    // 调用 Python 进行异步大批量运算
    if (window.pywebview) {
        window.pywebview.api.run_processing(
            invPath, 
            inputPath, 
            colName, 
            writeColName,
            prefix, 
            threshold, 
            mode,
            libraryType === 'google',
            googleSheetUrl,
            googleSheetName,
            googleCredsPath,
            inputType === 'google',
            googleInputUrl,
            googleInputName,
            aiClassifyEnable,
            aiApiKey,
            aiModel,
            aiBatchSize,
            aiConcurrency,
            aiColName,
            aiRules,
            translateMode,
            aiApiKey,
            aiPlatform,
            translateModel,  // 翻译专用模型，独立于分类模型
            ""
        );
    }
}

// 更新界面状态
function setUiState(isProcessing, processType) {
    const btn = document.getElementById('btn-run');
    const aiBtn = document.getElementById('btn-ai-run');
    const transBtn = document.getElementById('btn-translate');
    if (isProcessing) {
        btn.disabled = true;
        if (aiBtn) aiBtn.disabled = true;
        if (transBtn) transBtn.disabled = true;
        
        if (processType === 'ai') {
            if (aiBtn) aiBtn.textContent = "⚡ AI 正在分类中...";
            btn.textContent = "🚀 开始查重匹配编号";
        } else if (processType === 'translate') {
            if (transBtn) transBtn.textContent = "⚡ 翻译进行中...";
            btn.textContent = "🚀 开始查重匹配编号";
            if (aiBtn) aiBtn.textContent = "🤖 开始 AI 智能分类";
        } else {
            btn.textContent = "⚡ 正在计算处理中...";
            if (aiBtn) aiBtn.textContent = "🤖 开始 AI 智能分类";
        }
        document.getElementById('inventory-path').disabled = true;
        document.getElementById('prefix-input').disabled = true;
        document.getElementById('mode-select').disabled = true;
        document.getElementById('threshold-slider').disabled = true;
        
        document.getElementById('google-sheet-url').disabled = true;
        document.getElementById('google-sheet-name-select').disabled = true;
        document.getElementById('google-creds-path').disabled = true;
        
        document.getElementById('google-input-url').disabled = true;
        document.getElementById('google-input-name-select').disabled = true;

        if (document.getElementById('btn-verify-inv-google')) document.getElementById('btn-verify-inv-google').disabled = true;
        if (document.getElementById('btn-verify-input-google')) document.getElementById('btn-verify-input-google').disabled = true;
    } else {
        btn.disabled = false;
        if (aiBtn) aiBtn.disabled = false;
        if (transBtn) transBtn.disabled = false;
        
        btn.textContent = "🚀 开始查重匹配编号";
        if (aiBtn) aiBtn.textContent = "🤖 开始 AI 智能分类";
        if (transBtn) transBtn.textContent = "🌐 单独翻译到一列";
        
        document.getElementById('inventory-path').disabled = false;
        document.getElementById('prefix-input').disabled = false;
        document.getElementById('mode-select').disabled = false;
        document.getElementById('threshold-slider').disabled = false;
        
        document.getElementById('google-sheet-url').disabled = false;
        document.getElementById('google-sheet-name-select').disabled = false;
        document.getElementById('google-creds-path').disabled = false;
        
        document.getElementById('google-input-url').disabled = false;
        document.getElementById('google-input-name-select').disabled = false;

        if (document.getElementById('btn-verify-inv-google')) document.getElementById('btn-verify-inv-google').disabled = false;
        if (document.getElementById('btn-verify-input-google')) document.getElementById('btn-verify-input-google').disabled = false;
    }
}

// 打开结果文件夹
function openOutputFolder() {
    if (window.pywebview && outputFilePath) {
        window.pywebview.api.open_folder(outputFilePath);
    }
}

// 辅助更新状态文本
function updateStatusText(msg) {
    document.getElementById('status-title').textContent = msg;
}

// ------------------ Python 线程回调函数 (挂载在全局 window) ------------------

// 1. 进度更新
window.updateProgress = function(progress, msg) {
    const percent = Math.round(progress * 100);
    document.getElementById('progress-bar-fill').style.width = percent + "%";
    document.getElementById('progress-percent').textContent = percent + "%";
    updateStatusText(msg);
};

// 2. 更新总数记录
window.updateTotalCount = function(total) {
    document.getElementById('stat-total').textContent = total;
};

// 3. 计算成功并展示结果
window.showResults = function(jsonString, matchedCount, newCount, outPath) {
    setUiState(false);
    outputFilePath = outPath;
    
    // 更新统计卡片
    document.getElementById('stat-matched').textContent = matchedCount;
    document.getElementById('stat-new').textContent = newCount;
    
    // 更新底部输出位置和打开按钮
    document.getElementById('output-filepath').textContent = "输出路径: " + outPath;
    document.getElementById('btn-open-folder').disabled = false;
    
    // 渲染预览表格
    let results;
    if (typeof jsonString === 'string') {
        results = JSON.parse(jsonString);
    } else {
        results = jsonString;
    }
    const tbody = document.getElementById('result-tbody');
    tbody.innerHTML = "";
    
    if (results.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;">无可比对的数据预览</td></tr>`;
        return;
    }
    
    results.forEach((row, index) => {
        const tr = document.createElement('tr');
        
        // 限制内容长度，超出显示省略号
        const rawContent = String(row.文案内容 || '');
        const rawBestMatch = String(row.最相似文案 || '');
        const shortContent = rawContent.length > 80 ? rawContent.substring(0, 80) + "..." : rawContent;
        const shortBestMatch = rawBestMatch.length > 80 ? rawBestMatch.substring(0, 80) + "..." : rawBestMatch;
        
        const aiClassTag = row.AI分类 ? `<div style="font-size:10px; font-weight:normal; opacity:0.75; margin-top:2px;">AI分类: ${row.AI分类}</div>` : '';
        const timeTag = row.入库时间 ? `<div style="font-size:9px; font-weight:normal; opacity:0.6; margin-top:2px; font-family:monospace;">${row.入库时间}</div>` : '';

        let statusColor = '#10b981'; // 默认绿色
        if (row.匹配状态.includes('新文案')) {
            statusColor = 'var(--accent-color)';
        } else if (row.匹配状态 === 'AI已分类') {
            statusColor = '#a855f7'; // 紫色
        }

        tr.innerHTML = `
            <td style="text-align: center;">${index + 1}</td>
            <td title="${rawContent}">${shortContent}</td>
            <td style="text-align: center; font-weight: bold; color: ${statusColor};">${row.匹配状态}${aiClassTag}</td>
            <td style="text-align: center;">${row.相似度}</td>
            <td title="${rawBestMatch}">${shortBestMatch || '-'}</td>
            <td style="text-align: center; font-weight: bold;">${row.分配编号}${timeTag}</td>
        `;
        tbody.appendChild(tr);
    });
    
    let successMsg = "🎉 匹配完成！\n数据结果已经导出至您的 Excel 表格中，本地库存也已同步更新！";
    if (results.length > 0 && results[0].匹配状态 === "AI已分类") {
        successMsg = "🎉 AI 智能分类完成！\n结果已经保存至您的文件中！";
        updateStatusText("✨ AI 智能分类圆满完成！");
    } else {
        updateStatusText("✨ 比对计算圆满完成！");
    }
    alert(successMsg);
};

// 4. 计算失败反馈
window.showError = function(errorMsg) {
    setUiState(false);
    updateStatusText("❌ 运行失败");
    document.getElementById('progress-bar-fill').style.width = "0%";
    document.getElementById('progress-percent').textContent = "0%";
    
    document.getElementById('result-tbody').innerHTML = `
        <tr>
            <td colspan="6" style="text-align:center; color: #ef4444; font-weight: bold;">
                计算失败：${errorMsg}
            </td>
        </tr>
    `;
    
    alert("❌ 软件处理出错:\n" + errorMsg);
};

// --- AI 智能分类辅助逻辑 ---
const DEFAULT_AI_RULES = `分类规则和优先级
1. 借势贴：
【优先级：极高】
【决定性特征】 内容围绕一个具体的、可验证的、具有高时效性（正在发生或持续造成影响）的社会热点事件展开，并将该事件与信仰联系起来。例如，某地发生的地震、洪水、空难等。即使该事件是即将发生且被普遍关注的，也属于此列。
【关键区分】 必须提及具体事件（如“德州洪水”、“8.8级地震”），区别于泛泛地提及“灾难”。

2. 主再来：
【优先级：极高】
【决定性特征】 文案明确谈论关于主再来的话题，通常与末世预言、警示等相关。

3. 神的救恩/拯救：
【优先级：高】
【决定性特征】 内容核心是关于神的救赎计划、拯救人类免于罪恶和死亡的主题。

4. 悔改类：
【优先级：高】
【决定性特征】 明确提及“悔改”，呼吁读者认罪、改变行为，或强调悔改的重要性。

5. 得救，进天国：
【优先级：高】
【决定性特征】 内容核心是关于如何“得救”或“进入天国”，通常与永恒的生命和归宿相关。`;

function toggleAiClassifyEnabled() {
    const isChecked = document.getElementById('ai-classify-enable').checked;
    const details = document.getElementById('ai-classify-details');
    if (isChecked) {
        details.style.display = 'block';
    } else {
        details.style.display = 'none';
    }
}

function onAiPlatformChange() {
    // 隐藏 Base URL 后无需任何操作
}

function onAiModelChange() {
    // 隐藏自定义模型后无需任何操作
}

// 独立启动 AI 智能分类
function startAiClassification() {
    const inputPath = document.getElementById('input-path').value.trim();
    const colName = document.getElementById('ai-column-select').value;
    const aiApiKey = document.getElementById('ai-api-key').value.trim();
    const aiPlatform = document.getElementById('ai-platform').value;
    const aiBaseUrl = "";
    const aiModel = document.getElementById('ai-model').value;
    const aiProxy = "";
    const aiBatchSize = parseInt(document.getElementById('ai-batch-size').value) || 100;
    const aiConcurrency = parseInt(document.getElementById('ai-concurrency').value) || 3;
    const aiColName = document.getElementById('ai-col-name').value.trim() || 'AI分类';
    const aiRules = document.getElementById('ai-rules').value;

    const googleCredsPath = document.getElementById('google-creds-path').value.trim();
    const googleInputUrl = document.getElementById('google-input-url').value.trim();
    const googleInputName = document.getElementById('google-input-name-select').value;

    if (inputType === 'local') {
        if (!inputPath) {
            alert("请选择需要分类的本地文案表格！");
            return;
        }
    } else {
        if (!googleInputUrl) {
            alert("请输入谷歌待分类表格链接 (Google Sheets URL)！");
            return;
        }
        if (!googleCredsPath) {
            alert("请选择谷歌服务账号凭证 JSON 文件！");
            return;
        }
    }

    if (!aiApiKey) {
        alert("请输入 AI 密钥 (Gemini / Vertex API Key)！");
        return;
    }

    const translateMode = document.getElementById('translate-mode').value;

    let finalModel = aiModel;

    // 锁定界面组件
    setUiState(true, 'ai');

    // 清空上次结果与状态
    document.getElementById('result-tbody').innerHTML = `
        <tr class="empty-placeholder">
            <td colspan="6">AI 正在分类中，请耐心等候...</td>
        </tr>
    `;
    document.getElementById('stat-total').textContent = "0";
    document.getElementById('stat-matched').textContent = "0";
    document.getElementById('stat-new').textContent = "0";
    document.getElementById('output-filepath').textContent = "";
    document.getElementById('btn-open-folder').disabled = true;

    // 自动展开日志面板以方便查看
    const logContainer = document.getElementById('log-container');
    if (!logContainer.classList.contains('expanded')) {
        logContainer.classList.add('expanded');
    }
    addLog('system', '[分类] 开始批量 AI 智能分类流程...');

    if (window.pywebview) {
        window.pywebview.api.run_ai_classification(
            inputPath,
            colName,
            inputType === 'google',
            googleInputUrl,
            googleInputName,
            googleCredsPath,
            aiApiKey,
            finalModel,
            aiBatchSize,
            aiConcurrency,
            aiColName,
            aiRules,
            aiPlatform,
            aiBaseUrl,
            aiProxy,
            translateMode
        );
    }
}

// 测试 AI 接口连接
function testAiConnection() {
    const aiApiKey = document.getElementById('ai-api-key').value.trim();
    const aiPlatform = document.getElementById('ai-platform').value;
    const aiBaseUrl = "";
    const aiModel = document.getElementById('ai-model').value;
    const aiProxy = "";

    if (!aiApiKey) {
        alert("请输入 AI 密钥 (Gemini / Vertex API Key)！");
        return;
    }

    let finalModel = aiModel;

    // 自动展开日志面板以方便用户查看
    const logContainer = document.getElementById('log-container');
    if (!logContainer.classList.contains('expanded')) {
        logContainer.classList.add('expanded');
    }

    addLog('system', '[测试] 正在触发后端接口测试...');
    if (window.pywebview) {
        window.pywebview.api.test_ai_connection(
            aiApiKey,
            finalModel,
            aiPlatform,
            aiBaseUrl,
            aiProxy
        );
    }
}

// 日志面板展开/折叠
function toggleLogPanel() {
    const logContainer = document.getElementById('log-container');
    logContainer.classList.toggle('expanded');
}

// 清空日志
function clearLogs(event) {
    if (event) {
        event.stopPropagation(); // 阻止事件冒泡
    }
    const logContent = document.getElementById('log-content');
    logContent.innerHTML = '<div class="log-line system">[系统] 日志控制台已清空。</div>';
}

// 添加日志行
function addLog(level, text) {
    const logContent = document.getElementById('log-content');
    if (!logContent) return;

    const line = document.createElement('div');
    line.className = `log-line ${level}`;
    
    // 获取当前时间戳 [HH:MM:SS]
    const now = new Date();
    const timeStr = `[${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}]`;
    
    line.textContent = `${timeStr} ${text}`;
    logContent.appendChild(line);
    
    // 自动滚动到底部
    logContent.scrollTop = logContent.scrollHeight;
}

// ==================== 翻译弹窗逻辑 ====================

/**
 * 打开翻译弹窗，并同步当前列选项和已保存的 API Key
 */
function openTranslateModal() {
    // 同步列选项到翻译弹窗中的列选择器
    const srcSelect = document.getElementById('column-select');
    const transColSelect = document.getElementById('trans-col-select');
    transColSelect.innerHTML = '<option value="">第一列 (默认)</option>';
    if (srcSelect) {
        Array.from(srcSelect.options).forEach(opt => {
            if (opt.value && opt.value !== '第一列 (默认)') {
                const newOpt = document.createElement('option');
                newOpt.value = opt.value;
                newOpt.textContent = opt.textContent;
                transColSelect.appendChild(newOpt);
            }
        });
        if (srcSelect.value && srcSelect.value !== '第一列 (默认)') {
            transColSelect.value = srcSelect.value;
        }
    }

    // 同步 API Key（与 AI 分类共用同一个 Key）
    const aiKeyElem = document.getElementById('ai-api-key');
    const transKeyElem = document.getElementById('trans-api-key');
    if (aiKeyElem && transKeyElem && !transKeyElem.value) {
        transKeyElem.value = aiKeyElem.value;
    }

    // 同步平台
    const aiPlatformElem = document.getElementById('ai-platform');
    const transPlatformElem = document.getElementById('trans-platform');
    if (aiPlatformElem && transPlatformElem) {
        transPlatformElem.value = aiPlatformElem.value;
    }

    // 同步模型（翻译模型单独选择，默认 2.5-flash）
    const savedTransModel = document.getElementById('translate-model');
    const transModelElem = document.getElementById('trans-model');
    if (savedTransModel && transModelElem && savedTransModel.value) {
        transModelElem.value = savedTransModel.value;
    }

    document.getElementById('translate-modal-overlay').classList.add('active');
}

/**
 * 关闭翻译弹窗
 */
function closeTranslateModal() {
    document.getElementById('translate-modal-overlay').classList.remove('active');
}

/**
 * 点击弹窗遮罩层时关闭
 */
function closeTranslateModalOnBg(event) {
    if (event.target === document.getElementById('translate-modal-overlay')) {
        closeTranslateModal();
    }
}

/**
 * 开始独立翻译任务
 */
function startTranslation() {
    const inputPath = document.getElementById('input-path').value.trim();
    const googleInputUrl = document.getElementById('google-input-url').value.trim();
    const googleInputName = document.getElementById('google-input-name-select').value;
    const googleCredsPath = document.getElementById('google-creds-path').value.trim();

    // 弹窗内字段
    const colName = document.getElementById('trans-col-select').value;
    const targetLang = document.getElementById('trans-target-lang').value;
    const outputCol = document.getElementById('trans-output-col').value.trim() || '翻译英文';
    const apiKey = document.getElementById('trans-api-key').value.trim();
    const platform = document.getElementById('trans-platform').value;
    const model = document.getElementById('trans-model').value;
    const batchSize = parseInt(document.getElementById('trans-batch-size').value) || 30;
    const concurrency = parseInt(document.getElementById('trans-concurrency').value) || 3;

    // 输入校验
    if (inputType === 'local') {
        if (!inputPath) {
            alert('请先在主界面选择待翻译的本地文案表格！');
            return;
        }
    } else {
        if (!googleInputUrl) {
            alert('请先在主界面配置谷歌待比对表格链接！');
            return;
        }
        if (!googleCredsPath) {
            alert('请先在主界面选择谷歌服务账号凭证 JSON 文件！');
            return;
        }
    }

    if (!apiKey) {
        alert('请输入 AI API Key (Gemini)！');
        return;
    }

    // 关闭弹窗，锁定界面
    closeTranslateModal();
    setUiState(true, 'translate');

    // 清空结果区
    document.getElementById('result-tbody').innerHTML = `
        <tr class="empty-placeholder">
            <td colspan="6">🌐 正在批量翻译中，请耐心等候...</td>
        </tr>
    `;
    document.getElementById('stat-total').textContent = '0';
    document.getElementById('stat-matched').textContent = '0';
    document.getElementById('stat-new').textContent = '0';
    document.getElementById('output-filepath').textContent = '';
    document.getElementById('btn-open-folder').disabled = true;

    // 展开日志面板
    const logContainer = document.getElementById('log-container');
    if (!logContainer.classList.contains('expanded')) {
        logContainer.classList.add('expanded');
    }
    addLog('system', '[翻译] 开始独立批量翻译流程...');

    if (window.pywebview) {
        window.pywebview.api.run_translation(
            inputPath,
            colName,
            targetLang,
            apiKey,
            platform,
            model,
            batchSize,
            concurrency,
            outputCol,
            inputType === 'google',
            googleInputUrl,
            googleInputName,
            googleCredsPath,
            ''
        );
    }
}

/**
 * 翻译完成回调（由 Python 后端通过 evaluate_js 调用）
 */
window.showTranslationResults = function(results, totalCount, outPath) {
    setUiState(false);
    outputFilePath = outPath;

    document.getElementById('stat-total').textContent = totalCount;
    document.getElementById('stat-matched').textContent = '-';
    document.getElementById('stat-new').textContent = '-';
    document.getElementById('output-filepath').textContent = '输出路径: ' + outPath;
    document.getElementById('btn-open-folder').disabled = false;

    // 渲染预览
    let rows;
    if (typeof results === 'string') {
        rows = JSON.parse(results);
    } else {
        rows = results;
    }
    const tbody = document.getElementById('result-tbody');
    tbody.innerHTML = '';

    if (!rows || rows.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;">无翻译数据预览</td></tr>';
    } else {
        rows.forEach((row, index) => {
            const tr = document.createElement('tr');
            const rawContent = String(row['文案内容'] || '');
            const rawTrans = String(row['翻译英文'] || '');
            const shortContent = rawContent.length > 80 ? rawContent.substring(0, 80) + '...' : rawContent;
            const shortTrans = rawTrans.length > 80 ? rawTrans.substring(0, 80) + '...' : rawTrans;
            tr.innerHTML = `
                <td style="text-align:center;">${index + 1}</td>
                <td title="${rawContent}">${shortContent}</td>
                <td style="text-align:center; font-weight:bold; color:#0ea5e9;">${row['匹配状态']}</td>
                <td style="text-align:center;">-</td>
                <td title="${rawTrans}" style="color:#0ea5e9; font-size:12px;">${shortTrans || '-'}</td>
                <td style="text-align:center;">N/A</td>
            `;
            tbody.appendChild(tr);
        });
    }

    updateStatusText('✨ 批量翻译完成！可继续运行匹配编号或 AI 分类。');
    alert(`🎉 批量翻译完成！\n已将翻译结果写入新列，文件已保存。\n\n您现在可以：\n1. 点击【🚀 开始查重匹配编号】进行匹配比对\n2. 点击【🤖 开始 AI 智能分类】进行分类\n\n输出路径：${outPath}`);
};
