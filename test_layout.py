import os
from PIL import Image
# PIL の Resampling 定数互換性を補う
Image.LINEAR = Image.BILINEAR

# Detectron2LayoutModel を直接サブモジュールからインポート
from layoutparser.models.detectron2.layoutmodel import Detectron2LayoutModel

# モデルファイルのパスを展開（チルダを正しく解決）
model_path = os.path.expanduser(
    "~/.cache/layoutparser/checkpoints/PubLayNet/model_final.pth"
)

# PubLayNet モデルを読み込む
model = Detectron2LayoutModel(
    config_path="lp://PubLayNet/faster_rcnn_R_50_FPN_3x/config",
    model_path=model_path,
    extra_config=["MODEL.ROI_HEADS.SCORE_THRESH_TEST", 0.5],
    label_map={0: "text"}
)

# テスト画像を開く
image = Image.open("sample_page.png")  # または sample_page.png に合わせる
layout = model.detect(image)
print(layout)
