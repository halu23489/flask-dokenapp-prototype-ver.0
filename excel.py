import pandas as pd

# Excelファイルを読み込む
file_path = '沈下測定(ｸﾞﾗﾌ)20250107(修正).xlsx'
df = pd.read_excel(file_path, sheet_name='Sheet1', engine='openpyxl')

# G列からARF列までのデータを抽出
data = df.loc[:, 'G':'ARF']

# データを8列ずつ縦に並べる
reshaped_data = pd.concat([data.iloc[:, i:i+8].stack().reset_index(drop=True) for i in range(0, len(data.columns), 8)], axis=1)

# 3列目の値を追加
reshaped_data['C'] = df.iloc[:, 2]

# 新しいシートに書き込む
with pd.ExcelWriter(file_path, engine='openpyxl', mode='a') as writer:
    reshaped_data.to_excel(writer, sheet_name='ReshapedData', index=False)

print("データの整形が完了しました。新しいシート 'ReshapedData' に保存されました。")