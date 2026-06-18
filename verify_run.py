import os
import pandas as pd
from matcher import CopywritingMatcher

def create_sample_files():
    # 1. 创建模拟的库存数据库
    db_data = {
        '编号': ['CPY_000001', 'CPY_000002', 'CPY_000003'],
        '文案内容': [
            'Met deze fantastische tips kun je gemakkelijk je huis organiseren en schoonmaken!',
            'Ontdek de beste deals van deze week en bespaar tot wel 50% op je aankopen.',
            'Leren programmeren met Python is erg leuk en opent vele deuren voor je carrière!'
        ],
        '入库时间': ['2026-06-15 09:00:00', '2026-06-15 09:00:00', '2026-06-15 09:00:00'],
        '匹配次数': [1, 2, 1]
    }
    df_db = pd.DataFrame(db_data)
    df_db.to_excel('verify_inventory.xlsx', index=False)
    print("已成功创建样本库存文件: verify_inventory.xlsx")

    # 2. 创建模拟的待处理文案文件
    input_data = {
        '序号': [1, 2, 3, 4, 5],
        '文案': [
            # 1. 与 CPY_000002 非常相似 (只是少了“de”以及大小写微调)
            'Ontdek beste deals van deze week en bespaar tot wel 50% op aankopen.',
            # 2. 完全相同于 CPY_000003 (除了前后空格)
            '   Leren programmeren met Python is erg leuk en opent vele deuren voor je carrière!   ',
            # 3. 完全不相关的新文案
            'Het weer is vandaag prachtig in Amsterdam, perfect voor een boottocht.',
            # 4. 也是新文案，但在本次处理中，第4条和第5条文案高度相似！
            'Reisgids voor een weekendje in Parijs met de beste hotspots en restaurants.',
            'Geweldige gids voor weekend in Parijs met hotspots en leuke restaurants.'
        ]
    }
    df_input = pd.DataFrame(input_data)
    df_input.to_excel('verify_input.xlsx', index=False)
    print("已成功创建待比对文案文件: verify_input.xlsx")

def run_verification():
    create_sample_files()
    
    # 初始化匹配器
    print("\n--- 启动 CopywritingMatcher ---")
    matcher = CopywritingMatcher(inventory_path='verify_inventory.xlsx', id_prefix='CPY_', threshold=0.60)
    
    # 读取输入文件
    df_input = pd.read_excel('verify_input.xlsx')
    new_texts = df_input['文案'].tolist()
    
    # 运行匹配
    results = matcher.process_batch(new_texts)
    
    # 输出结果
    df_output = df_input.copy()
    df_output['分配编号'] = [r['分配编号'] for r in results]
    df_output['匹配状态'] = [r['匹配状态'] for r in results]
    df_output['相似度'] = [r['相似度'] for r in results]
    df_output['最相似文案'] = [r['最相似文案'] for r in results]
    
    df_output.to_excel('verify_result.xlsx', index=False)
    print("匹配计算完成！结果已写入 verify_result.xlsx")
    
    # 打印终端结果对比
    print("\n--- 匹配结果详情预览 ---")
    for idx, row in df_output.iterrows():
        print(f"新文案: {row['文案'][:40].strip()}...")
        print(f"  -> 状态: {row['匹配状态']} | 相似度: {row['相似度']} | 分配编号: {row['分配编号']}")
        if row['最相似文案']:
            print(f"  -> 最相似原句: {row['最相似文案'][:40]}...")
        print()
        
    # 验证数据库是否更新
    print("--- 验证库存数据库最终状态 ---")
    updated_db = pd.read_excel('verify_inventory.xlsx')
    print(updated_db[['编号', '匹配次数', '文案内容']])
    
    # 检查第4条和第5条新文案是否共享了同一个新ID
    id_4 = df_output.loc[3, '分配编号']
    id_5 = df_output.loc[4, '分配编号']
    print(f"\n文案 4 分配的编号: {id_4}")
    print(f"文案 5 分配的编号: {id_5}")
    if id_4 == id_5:
        print("🎉 成功：即使是新文案，如果新文案之间相似，也分配了同一个新编号！")
    else:
        print("❌ 失败：新文案之间相似，但分配了不同的编号。")

if __name__ == "__main__":
    run_verification()
