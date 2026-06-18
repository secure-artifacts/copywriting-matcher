/* -------------------------------------------------------------
 * 爆贴文案查重与库存管理系统 - 前端交互逻辑 JS
 * ------------------------------------------------------------- */

let selectedInputPath = "";

// 全局配置状态对象
let currentSettings = {
    theme: 'dark',
    bgImage: '',
    blur: 10,
    opacity: 75,
    inventoryPath: '',
    prefix: 'CPY_',
    mode: 'tfidf',
    threshold: 80
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
        } else {
            window.pywebview.api.get_default_inventory_path().then(function(path) {
                document.getElementById('inventory-path').value = path;
            });
        }
    });
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
                    const colSelect = document.getElementById('column-select');
                    colSelect.innerHTML = "";
                    
                    if (cols && cols.error) {
                        alert("解析表格表头失败:\n" + cols.error);
                        updateStatusText("❌ 载入文件错误");
                        return;
                    }
                    
                    if (Array.isArray(cols) && cols.length > 0) {
                        cols.forEach(col => {
                            const opt = document.createElement('option');
                            opt.value = col;
                            opt.textContent = col;
                            colSelect.appendChild(opt);
                        });
                        colSelect.disabled = false;
                        
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
                        updateStatusText("✅ 表格导入成功，点击下方按钮开始比对。");
                    } else {
                        const opt = document.createElement('option');
                        opt.textContent = "第一列 (默认)";
                        colSelect.appendChild(opt);
                        colSelect.disabled = true;
                        updateStatusText("⚠️ 未能识别列名，默认使用第一列。");
                    }
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
    const prefix = document.getElementById('prefix-input').value.trim();
    const threshold = document.getElementById('threshold-slider').value / 100;
    const mode = document.getElementById('mode-select').value;

    if (!invPath) {
        alert("请输入或选择库存文件路径！");
        return;
    }
    if (!inputPath) {
        alert("请选择需要处理的新文案表格！");
        return;
    }
    if (!prefix) {
        alert("编号前缀不能为空！");
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
        window.pywebview.api.run_processing(invPath, inputPath, colName, prefix, threshold, mode);
    }
}

// 更新界面状态
function setUiState(isProcessing) {
    const btn = document.getElementById('btn-run');
    if (isProcessing) {
        btn.disabled = true;
        btn.textContent = "⚡ 正在计算处理中...";
        document.getElementById('inventory-path').disabled = true;
        document.getElementById('prefix-input').disabled = true;
        document.getElementById('mode-select').disabled = true;
        document.getElementById('threshold-slider').disabled = true;
    } else {
        btn.disabled = false;
        btn.textContent = "🚀 开始比对处理";
        document.getElementById('inventory-path').disabled = false;
        document.getElementById('prefix-input').disabled = false;
        document.getElementById('mode-select').disabled = false;
        document.getElementById('threshold-slider').disabled = false;
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
    const results = JSON.parse(jsonString);
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
        
        tr.innerHTML = `
            <td style="text-align: center;">${index + 1}</td>
            <td title="${rawContent}">${shortContent}</td>
            <td style="text-align: center; font-weight: bold; color: ${row.匹配状态.includes('新文案') ? 'var(--accent-color)' : '#10b981'};">${row.匹配状态}</td>
            <td style="text-align: center;">${row.相似度}</td>
            <td title="${rawBestMatch}">${shortBestMatch || '-'}</td>
            <td style="text-align: center; font-weight: bold;">${row.分配编号}</td>
        `;
        tbody.appendChild(tr);
    });
    
    updateStatusText("✨ 比对计算圆满完成！");
    alert("🎉 匹配完成！\n数据结果已经导出至您的 Excel 表格中，本地库存也已同步更新！");
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
