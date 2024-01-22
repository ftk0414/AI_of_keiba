import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.ndimage import rotate

# CSVファイルを読み込む
file_path = '/Users/hjm.f/Desktop/smoothed_corners_surface_data.csv'  # 実際のCSVファイルのパスに置き換えてください
df = pd.read_csv(file_path)

# CSVデータをNumPy配列に変換
data = df.to_numpy()

# グラフ上で点を選択するための関数
def select_points_on_graph(data, num_points=4):
    fig, ax = plt.subplots()
    im = ax.imshow(data, cmap='viridis')
    points = []

    def onclick(event):
        if event.xdata is not None and event.ydata is not None:
            x, y = int(event.xdata), int(event.ydata)
            z = data[y, x]
            points.append((x, y, z))
            if len(points) == num_points:
                fig.canvas.mpl_disconnect(cid)
                plt.close(fig)

    cid = fig.canvas.mpl_connect('button_press_event', onclick)
    plt.show()
    return points

# 4点を選択
selected_points = select_points_on_graph(data)
print(selected_points)

# 傾き補正の計算
def calculate_tilt_correction(data, points, xy_spacing):

    # 平行移動のためのZ座標の平均を計算
    mean_z = np.mean([p[2] for p in points])

    # データ全体を平行移動して選択された点のZ座標を0にする
    shifted_data = data - mean_z

    # Y軸周りの傾き（X-Z平面）
    p1, p2 = points[0], points[1]
    tilt_y = np.arctan2(p2[2] - p1[2], (p2[0] - p1[0]) * xy_spacing) * 180 / np.pi
    
    # X軸周りの傾き（Y-Z平面）
    p3, p4 = points[2], points[3]
    tilt_x = np.arctan2(p4[2] - p3[2], (p4[1] - p3[1]) * xy_spacing) * 180 / np.pi

    # 傾き補正
    corrected_data_y = rotate(data, -tilt_y, axes=(1, 0), reshape=False)
    corrected_data = rotate(corrected_data_y, -tilt_x, axes=(0, 1), reshape=False)

    return corrected_data

# 傾き補正を実行
corrected_data = calculate_tilt_correction(data, selected_points, 0.5)  # 0.5μmはXとYの間隔

# 補正後のデータを表示
plt.imshow(corrected_data, cmap='viridis')
plt.colorbar(label='Height (μm)')
plt.title('Tilt Corrected Surface Data')
plt.show()