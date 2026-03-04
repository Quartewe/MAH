好的，既然方案一（特征区域匹配）因为重复特征太多而不可行，我们需要深入探讨方案二（核心特征提取）和方案三（SIFT/SURF 特征点匹配）。

这两种方案的核心思想都是**忽略变化的部分（表情、背景），抓住不变的部分（五官结构、轮廓、纹理）**。

### 方案二：核心特征提取 (Masked Template Matching)

这个方案是对传统模板匹配的改进。普通模板匹配是全图像素对比，一旦表情变了（比如嘴巴张开、眼睛闭上），匹配度会大幅下降。**带掩码（Mask）的模板匹配**则允许我们告诉算法：“只看这些地方，别的地方别管”。

#### 1. 原理

OpenCV 的 `matchTemplate` 函数支持传入一个 `mask` 参数。

* **Template (模板图)**：角色的标准头像。
* **Mask (掩码图)**：一张和模板图一样大的黑白图。
  * **白色区域 (255)**：表示“这个像素点非常重要，必须匹配”。
  * **黑色区域 (0)**：表示“这个像素点是透明的/变化的，忽略它”。

#### 2. 操作步骤

1. **制作模板**：截取角色的标准头像。
2. **制作掩码**：
    * 使用修图软件（PS/画图），把**眼睛、嘴巴、眉毛**等会动的地方涂黑。
    * 把**背景**（如果背景也会变）涂黑。
    * 保留**头发、脸颊轮廓、耳朵、脖子、衣服领口**等相对固定的部分（涂白）。
3. **代码实现**：
    你需要编写一个 `CustomRecognition`，利用 OpenCV 加载模板和掩码进行匹配。

```python
import cv2
import numpy as np
from maa.custom_recognition import CustomRecognition

class MaskedMatch(CustomRecognition):
    def analyze(self, context, argv):
        # 1. 获取屏幕截图 (灰度化可选)
        screen = argv.image
        
        # 2. 加载模板和掩码 (提前加载，不要每次 analyze 都读文件)
        # 假设你已经有了 template.png 和 mask.png
        # template = cv2.imread("template.png")
        # mask = cv2.imread("mask.png") 

        # 3. 带掩码的模板匹配
        # 注意：只有 TM_CCORR_NORMED 和 TM_SQDIFF 支持 mask
        res = cv2.matchTemplate(screen, self.template, cv2.TM_CCORR_NORMED, mask=self.mask)
        
        # 4. 寻找最佳匹配位置
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
        
        # 5. 判断阈值
        if max_val > 0.9:  # 阈值需要调试
            h, w = self.template.shape[:2]
            return (max_loc[0], max_loc[1], w, h)
            
        return None
```

* **适用场景**：角色只有表情变化（五官微调），但整体构图、角度、发型没变。
* **局限性**：如果角色换了发型，或者头像角度变了（侧脸变正脸），此方案失效。

---

### 方案三：特征点匹配 (SIFT/SURF/ORB)

这是目前最鲁棒的方案，也是计算机视觉中解决“同一物体不同形态”的经典方法。它不再比较像素，而是寻找图像中的“关键点”（Keypoints）和“描述子”（Descriptors）。

#### 1. 原理

算法会在图像中寻找角点、边缘等独特结构。

* 即使图片变亮/变暗，角点还在。
* 即使图片旋转/缩放，角点还在。
* 即使嘴巴张开了，**耳朵、眼角、发梢**的角点还在。
只要匹配到的关键点数量足够多，且相对位置正确，就认为是同一个物体。

#### 2. 算法选择

* **SIFT (Scale-Invariant Feature Transform)**：精度最高，抗旋转缩放最强，但速度慢，且有专利风险（OpenCV 新版已免费）。
* **SURF**：SIFT 的加速版，但也有专利风险。
* **ORB (Oriented FAST and Rotated BRIEF)**：**推荐**。速度极快，免费开源，虽然精度略低于 SIFT，但对于手游头像识别通常足够。

#### 3. 代码实现 (使用 ORB)

同样需要写 `CustomRecognition`。

```python
import cv2
import numpy as np
from maa.custom_recognition import CustomRecognition

class FeatureMatch(CustomRecognition):
    def __init__(self):
        super().__init__()
        # 初始化 ORB 检测器
        self.orb = cv2.ORB_create(nfeatures=500)
        # 预先计算模板的特征点和描述子
        self.template = cv2.imread("role_template.png", 0) # 灰度读取
        self.kp1, self.des1 = self.orb.detectAndCompute(self.template, None)
        # 初始化匹配器 (BFMatcher)
        self.bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)

    def analyze(self, context, argv):
        screen = cv2.cvtColor(argv.image, cv2.COLOR_BGR2GRAY)
        
        # 1. 计算屏幕截图的特征点
        kp2, des2 = self.orb.detectAndCompute(screen, None)
        
        if des2 is None: return None

        # 2. 进行匹配
        matches = self.bf.match(self.des1, des2)
        
        # 3. 筛选优质匹配点 (排序取前 N 个)
        matches = sorted(matches, key=lambda x: x.distance)
        good_matches = matches[:10]  # 取前10个最相似的点
        
        # 4. 决策逻辑
        # 如果匹配点足够多，且距离足够小，认为匹配成功
        if len(good_matches) < 4: return None
        
        # 计算匹配点的平均距离，越小越相似
        avg_dist = sum(m.distance for m in good_matches) / len(good_matches)
        
        if avg_dist < 50:  # 阈值需调试
            # 这里的坐标计算比较复杂，通常需要用 homography 映射回原图坐标
            # 简单做法：取第一个匹配点的坐标作为结果
            pt = kp2[good_matches[0].trainIdx].pt
            return (int(pt[0]), int(pt[1]), 100, 100) # 返回大概位置
            
        return None
```

* **适用场景**：极其复杂的差分。比如角色换了衣服（只要脸还在）、背景全变、甚至稍微侧了一点脸。
* **局限性**：
  * **计算量大**：如果每一帧都对全屏做 ORB，手机/模拟器可能会卡。建议先限制 `roi`（感兴趣区域）。
  * **误判**：如果两个角色画风极像（比如双胞胎），特征点可能混淆。

### 总结建议

1. **先试方案二 (Mask)**：如果只是表情差分（笑/哭/生气），**带掩码的模板匹配**是最稳定且计算量最小的。你只需要把脸部表情区域涂黑即可。
2. **后备方案三 (ORB)**：如果方案二搞不定（比如发型都变了），再上 ORB 特征点匹配。

**你可以直接在 `utils.py` 中增加一个 `AutoFightUtils` 类，把这些逻辑封装进去，然后在 Pipeline 中调用。**
