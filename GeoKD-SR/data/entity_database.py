"""
地理实体库
包含中国主要地理实体的坐标和属性信息
"""
import json
from typing import List, Dict, Any


# 省级行政区（34个）
PROVINCES = [
    {"name": "北京市", "type": "municipality", "lat": 39.9042, "lon": 116.4074},
    {"name": "天津市", "type": "municipality", "lat": 39.0842, "lon": 117.2010},
    {"name": "河北省", "type": "province", "lat": 38.0428, "lon": 114.5149},
    {"name": "山西省", "type": "province", "lat": 37.5707, "lon": 111.8499},
    {"name": "内蒙古自治区", "type": "autonomous_region", "lat": 40.8414, "lon": 111.7519},
    {"name": "辽宁省", "type": "province", "lat": 41.2956, "lon": 123.4315},
    {"name": "吉林省", "type": "province", "lat": 43.8868, "lon": 125.3245},
    {"name": "黑龙江省", "type": "province", "lat": 45.7732, "lon": 126.6499},
    {"name": "上海市", "type": "municipality", "lat": 31.2304, "lon": 121.4737},
    {"name": "江苏省", "type": "province", "lat": 32.0603, "lon": 118.7969},
    {"name": "浙江省", "type": "province", "lat": 30.2741, "lon": 120.1551},
    {"name": "安徽省", "type": "province", "lat": 31.8612, "lon": 117.2272},
    {"name": "福建省", "type": "province", "lat": 26.0745, "lon": 119.2965},
    {"name": "江西省", "type": "province", "lat": 28.6769, "lon": 115.9099},
    {"name": "山东省", "type": "province", "lat": 36.6683, "lon": 117.0204},
    {"name": "河南省", "type": "province", "lat": 34.7466, "lon": 113.6253},
    {"name": "湖北省", "type": "province", "lat": 30.5928, "lon": 114.3055},
    {"name": "湖南省", "type": "province", "lat": 28.2282, "lon": 112.9388},
    {"name": "广东省", "type": "province", "lat": 23.3790, "lon": 116.6832},
    {"name": "广西壮族自治区", "type": "autonomous_region", "lat": 22.8155, "lon": 108.3275},
    {"name": "海南省", "type": "province", "lat": 20.0174, "lon": 110.3492},
    {"name": "重庆市", "type": "municipality", "lat": 29.4316, "lon": 106.9123},
    {"name": "四川省", "type": "province", "lat": 30.6171, "lon": 104.0648},
    {"name": "贵州省", "type": "province", "lat": 26.5783, "lon": 106.7135},
    {"name": "云南省", "type": "province", "lat": 25.0443, "lon": 102.7046},
    {"name": "西藏自治区", "type": "autonomous_region", "lat": 29.6524, "lon": 91.1721},
    {"name": "陕西省", "type": "province", "lat": 34.3416, "lon": 108.9398},
    {"name": "甘肃省", "type": "province", "lat": 36.0611, "lon": 103.8343},
    {"name": "青海省", "type": "province", "lat": 36.6171, "lon": 101.7782},
    {"name": "宁夏回族自治区", "type": "autonomous_region", "lat": 38.4681, "lon": 106.2731},
    {"name": "新疆维吾尔自治区", "type": "autonomous_region", "lat": 43.7930, "lon": 87.6177},
    {"name": "香港特别行政区", "type": "sar", "lat": 22.3193, "lon": 114.1694},
    {"name": "澳门特别行政区", "type": "sar", "lat": 22.1987, "lon": 113.5439},
    {"name": "台湾省", "type": "province", "lat": 25.0330, "lon": 121.5654},
]

# 主要城市（100+）
CITIES = [
    # 省会城市
    {"name": "石家庄", "type": "city", "lat": 38.0428, "lon": 114.5149, "province": "河北省"},
    {"name": "太原", "type": "city", "lat": 37.8706, "lon": 112.5489, "province": "山西省"},
    {"name": "呼和浩特", "type": "city", "lat": 40.8414, "lon": 111.7519, "province": "内蒙古自治区"},
    {"name": "沈阳", "type": "city", "lat": 41.8057, "lon": 123.4315, "province": "辽宁省"},
    {"name": "长春", "type": "city", "lat": 43.8868, "lon": 125.3245, "province": "吉林省"},
    {"name": "哈尔滨", "type": "city", "lat": 45.8038, "lon": 126.5340, "province": "黑龙江省"},
    {"name": "南京", "type": "city", "lat": 32.0603, "lon": 118.7969, "province": "江苏省"},
    {"name": "杭州", "type": "city", "lat": 30.2741, "lon": 120.1551, "province": "浙江省"},
    {"name": "合肥", "type": "city", "lat": 31.8206, "lon": 117.2272, "province": "安徽省"},
    {"name": "福州", "type": "city", "lat": 26.0745, "lon": 119.2965, "province": "福建省"},
    {"name": "南昌", "type": "city", "lat": 28.6769, "lon": 115.9099, "province": "江西省"},
    {"name": "济南", "type": "city", "lat": 36.6512, "lon": 117.1205, "province": "山东省"},
    {"name": "郑州", "type": "city", "lat": 34.7466, "lon": 113.6253, "province": "河南省"},
    {"name": "武汉", "type": "city", "lat": 30.5928, "lon": 114.3055, "province": "湖北省"},
    {"name": "长沙", "type": "city", "lat": 28.2282, "lon": 112.9388, "province": "湖南省"},
    {"name": "广州", "type": "city", "lat": 23.1291, "lon": 113.2644, "province": "广东省"},
    {"name": "南宁", "type": "city", "lat": 22.8170, "lon": 108.3665, "province": "广西壮族自治区"},
    {"name": "海口", "type": "city", "lat": 20.0440, "lon": 110.1999, "province": "海南省"},
    {"name": "成都", "type": "city", "lat": 30.5728, "lon": 104.0668, "province": "四川省"},
    {"name": "贵阳", "type": "city", "lat": 26.6470, "lon": 106.6302, "province": "贵州省"},
    {"name": "昆明", "type": "city", "lat": 25.0443, "lon": 102.7046, "province": "云南省"},
    {"name": "拉萨", "type": "city", "lat": 29.6524, "lon": 91.1721, "province": "西藏自治区"},
    {"name": "西安", "type": "city", "lat": 34.3416, "lon": 108.9398, "province": "陕西省"},
    {"name": "兰州", "type": "city", "lat": 36.0611, "lon": 103.8343, "province": "甘肃省"},
    {"name": "西宁", "type": "city", "lat": 36.6171, "lon": 101.7782, "province": "青海省"},
    {"name": "银川", "type": "city", "lat": 38.4681, "lon": 106.2731, "province": "宁夏回族自治区"},
    {"name": "乌鲁木齐", "type": "city", "lat": 43.8256, "lon": 87.6168, "province": "新疆维吾尔自治区"},

    # 重要城市
    {"name": "深圳", "type": "city", "lat": 22.5431, "lon": 114.0579, "province": "广东省"},
    {"name": "珠海", "type": "city", "lat": 22.2769, "lon": 113.5678, "province": "广东省"},
    {"name": "汕头", "type": "city", "lat": 23.3540, "lon": 116.6820, "province": "广东省"},
    {"name": "佛山", "type": "city", "lat": 23.0218, "lon": 113.1219, "province": "广东省"},
    {"name": "东莞", "type": "city", "lat": 23.0205, "lon": 113.7518, "province": "广东省"},
    {"name": "苏州", "type": "city", "lat": 31.2989, "lon": 120.5853, "province": "江苏省"},
    {"name": "无锡", "type": "city", "lat": 31.4912, "lon": 120.3119, "province": "江苏省"},
    {"name": "常州", "type": "city", "lat": 31.8106, "lon": 119.9741, "province": "江苏省"},
    {"name": "宁波", "type": "city", "lat": 29.8683, "lon": 121.5440, "province": "浙江省"},
    {"name": "温州", "type": "city", "lat": 28.0000, "lon": 120.6667, "province": "浙江省"},
    {"name": "嘉兴", "type": "city", "lat": 30.7528, "lon": 120.7549, "province": "浙江省"},
    {"name": "湖州", "type": "city", "lat": 30.8941, "lon": 120.0867, "province": "浙江省"},
    {"name": "绍兴", "type": "city", "lat": 30.0319, "lon": 120.5820, "province": "浙江省"},
    {"name": "金华", "type": "city", "lat": 29.0787, "lon": 119.6479, "province": "浙江省"},
    {"name": "台州", "type": "city", "lat": 28.6563, "lon": 121.4287, "province": "浙江省"},
    {"name": "丽水", "type": "city", "lat": 28.4689, "lon": 119.9229, "province": "浙江省"},
    {"name": "衢州", "type": "city", "lat": 28.9358, "lon": 118.8597, "province": "浙江省"},
    {"name": "舟山", "type": "city", "lat": 30.0360, "lon": 122.1064, "province": "浙江省"},
    {"name": "厦门", "type": "city", "lat": 24.4798, "lon": 118.0894, "province": "福建省"},
    {"name": "泉州", "type": "city", "lat": 24.8741, "lon": 118.6757, "province": "福建省"},
    {"name": "漳州", "type": "city", "lat": 24.5130, "lon": 117.6471, "province": "福建省"},
    {"name": "莆田", "type": "city", "lat": 25.4541, "lon": 119.0078, "province": "福建省"},
    {"name": "三明", "type": "city", "lat": 26.2634, "lon": 117.6389, "province": "福建省"},
    {"name": "南平", "type": "city", "lat": 26.6418, "lon": 118.1777, "province": "福建省"},
    {"name": "龙岩", "type": "city", "lat": 25.0616, "lon": 117.0176, "province": "福建省"},
    {"name": "宁德", "type": "city", "lat": 26.6617, "lon": 119.5477, "province": "福建省"},
    {"name": "青岛", "type": "city", "lat": 36.0671, "lon": 120.3826, "province": "山东省"},
    {"name": "烟台", "type": "city", "lat": 37.4637, "lon": 121.4479, "province": "山东省"},
    {"name": "潍坊", "type": "city", "lat": 36.7069, "lon": 119.1619, "province": "山东省"},
    {"name": "淄博", "type": "city", "lat": 36.8131, "lon": 118.0548, "province": "山东省"},
    {"name": "威海", "type": "city", "lat": 37.5131, "lon": 122.1202, "province": "山东省"},
    {"name": "日照", "type": "city", "lat": 35.4164, "lon": 119.5269, "province": "山东省"},
    {"name": "临沂", "type": "city", "lat": 35.1041, "lon": 118.3561, "province": "山东省"},
    {"name": "东营", "type": "city", "lat": 37.4347, "lon": 118.6752, "province": "山东省"},
    {"name": "德州", "type": "city", "lat": 37.4355, "lon": 116.3575, "province": "山东省"},
    {"name": "聊城", "type": "city", "lat": 36.4559, "lon": 115.9853, "province": "山东省"},
    {"name": "滨州", "type": "city", "lat": 37.3835, "lon": 117.9708, "province": "山东省"},
    {"name": "菏泽", "type": "city", "lat": 35.2339, "lon": 115.4807, "province": "山东省"},
    {"name": "枣庄", "type": "city", "lat": 34.8107, "lon": 117.3237, "province": "山东省"},
    {"name": "大连", "type": "city", "lat": 38.9140, "lon": 121.6147, "province": "辽宁省"},
    {"name": "鞍山", "type": "city", "lat": 41.1087, "lon": 122.9956, "province": "辽宁省"},
    {"name": "抚顺", "type": "city", "lat": 41.8773, "lon": 123.9573, "province": "辽宁省"},
    {"name": "本溪", "type": "city", "lat": 41.2978, "lon": 123.7674, "province": "辽宁省"},
    {"name": "丹东", "type": "city", "lat": 40.1290, "lon": 124.3854, "province": "辽宁省"},
    {"name": "锦州", "type": "city", "lat": 41.0956, "lon": 121.1269, "province": "辽宁省"},
    {"name": "营口", "type": "city", "lat": 40.6678, "lon": 122.2350, "province": "辽宁省"},
    {"name": "阜新", "type": "city", "lat": 42.0215, "lon": 121.6709, "province": "辽宁省"},
    {"name": "辽阳", "type": "city", "lat": 41.2698, "lon": 123.2403, "province": "辽宁省"},
    {"name": "盘锦", "type": "city", "lat": 41.1198, "lon": 122.0707, "province": "辽宁省"},
    {"name": "铁岭", "type": "city", "lat": 42.2906, "lon": 123.8416, "province": "辽宁省"},
    {"name": "朝阳", "type": "city", "lat": 41.5757, "lon": 120.4508, "province": "辽宁省"},
    {"name": "葫芦岛", "type": "city", "lat": 40.7430, "lon": 120.8375, "province": "辽宁省"},
    {"name": "吉林", "type": "city", "lat": 43.8378, "lon": 126.5496, "province": "吉林省"},
    {"name": "四平", "type": "city", "lat": 43.1701, "lon": 124.3506, "province": "吉林省"},
    {"name": "辽源", "type": "city", "lat": 42.9024, "lon": 125.1434, "province": "吉林省"},
    {"name": "通化", "type": "city", "lat": 41.7285, "lon": 125.9395, "province": "吉林省"},
    {"name": "白山", "type": "city", "lat": 41.9374, "lon": 126.4146, "province": "吉林省"},
    {"name": "松原", "type": "city", "lat": 45.1411, "lon": 124.8250, "province": "吉林省"},
    {"name": "白城", "type": "city", "lat": 45.6197, "lon": 122.8389, "province": "吉林省"},
    {"name": "齐齐哈尔", "type": "city", "lat": 47.3540, "lon": 123.9180, "province": "黑龙江省"},
    {"name": "鸡西", "type": "city", "lat": 45.2956, "lon": 130.9697, "province": "黑龙江省"},
    {"name": "鹤岗", "type": "city", "lat": 47.3500, "lon": 130.2979, "province": "黑龙江省"},
    {"name": "双鸭山", "type": "city", "lat": 46.6463, "lon": 131.1590, "province": "黑龙江省"},
    {"name": "大庆", "type": "city", "lat": 46.5879, "lon": 125.1033, "province": "黑龙江省"},
    {"name": "伊春", "type": "city", "lat": 47.7273, "lon": 128.8990, "province": "黑龙江省"},
    {"name": "佳木斯", "type": "city", "lat": 46.7995, "lon": 130.3187, "province": "黑龙江省"},
    {"name": "七台河", "type": "city", "lat": 45.7710, "lon": 131.0031, "province": "黑龙江省"},
    {"name": "牡丹江", "type": "city", "lat": 44.5526, "lon": 129.6333, "province": "黑龙江省"},
    {"name": "黑河", "type": "city", "lat": 50.2456, "lon": 127.5289, "province": "黑龙江省"},
    {"name": "绥化", "type": "city", "lat": 46.6374, "lon": 126.9695, "province": "黑龙江省"},
    {"name": "包头", "type": "city", "lat": 40.6574, "lon": 109.8403, "province": "内蒙古自治区"},
    {"name": "乌海", "type": "city", "lat": 39.6542, "lon": 106.8254, "province": "内蒙古自治区"},
    {"name": "赤峰", "type": "city", "lat": 42.2573, "lon": 118.8869, "province": "内蒙古自治区"},
    {"name": "通辽", "type": "city", "lat": 43.6174, "lon": 122.2432, "province": "内蒙古自治区"},
    {"name": "鄂尔多斯", "type": "city", "lat": 39.6086, "lon": 109.7816, "province": "内蒙古自治区"},
    {"name": "呼伦贝尔", "type": "city", "lat": 49.2122, "lon": 119.7659, "province": "内蒙古自治区"},
    {"name": "巴彦淖尔", "type": "city", "lat": 40.7431, "lon": 107.3879, "province": "内蒙古自治区"},
    {"name": "乌兰察布", "type": "city", "lat": 40.9944, "lon": 113.1327, "province": "内蒙古自治区"},
    {"name": "桂林", "type": "city", "lat": 25.2736, "lon": 110.2900, "province": "广西壮族自治区"},
    {"name": "柳州", "type": "city", "lat": 24.3264, "lon": 109.4281, "province": "广西壮族自治区"},
    {"name": "梧州", "type": "city", "lat": 23.4768, "lon": 111.2790, "province": "广西壮族自治区"},
    {"name": "北海", "type": "city", "lat": 21.4733, "lon": 109.1198, "province": "广西壮族自治区"},
    {"name": "防城港", "type": "city", "lat": 21.6145, "lon": 108.3547, "province": "广西壮族自治区"},
    {"name": "钦州", "type": "city", "lat": 21.9731, "lon": 108.6542, "province": "广西壮族自治区"},
    {"name": "贵港", "type": "city", "lat": 23.1036, "lon": 109.5986, "province": "广西壮族自治区"},
    {"name": "玉林", "type": "city", "lat": 22.6540, "lon": 110.1808, "province": "广西壮族自治区"},
    {"name": "百色", "type": "city", "lat": 23.9025, "lon": 106.6182, "province": "广西壮族自治区"},
    {"name": "贺州", "type": "city", "lat": 24.4032, "lon": 111.5526, "province": "广西壮族自治区"},
    {"name": "河池", "type": "city", "lat": 24.6929, "lon": 108.0854, "province": "广西壮族自治区"},
    {"name": "来宾", "type": "city", "lat": 23.7520, "lon": 109.2218, "province": "广西壮族自治区"},
    {"name": "崇左", "type": "city", "lat": 22.3769, "lon": 107.3646, "province": "广西壮族自治区"},
    {"name": "绵阳", "type": "city", "lat": 31.4678, "lon": 104.6794, "province": "四川省"},
    {"name": "自贡", "type": "city", "lat": 29.3393, "lon": 104.7784, "province": "四川省"},
    {"name": "攀枝花", "type": "city", "lat": 26.5804, "lon": 101.7188, "province": "四川省"},
    {"name": "泸州", "type": "city", "lat": 28.8719, "lon": 105.4420, "province": "四川省"},
    {"name": "德阳", "type": "city", "lat": 31.1270, "lon": 104.3980, "province": "四川省"},
    {"name": "广元", "type": "city", "lat": 32.4354, "lon": 105.8431, "province": "四川省"},
    {"name": "遂宁", "type": "city", "lat": 30.5134, "lon": 105.5929, "province": "四川省"},
    {"name": "内江", "type": "city", "lat": 29.5834, "lon": 105.0583, "province": "四川省"},
    {"name": "乐山", "type": "city", "lat": 29.5520, "lon": 103.7656, "province": "四川省"},
    {"name": "南充", "type": "city", "lat": 30.8373, "lon": 106.1106, "province": "四川省"},
    {"name": "眉山", "type": "city", "lat": 30.0492, "lon": 103.8484, "province": "四川省"},
    {"name": "宜宾", "type": "city", "lat": 28.7696, "lon": 104.6430, "province": "四川省"},
    {"name": "广安", "type": "city", "lat": 30.4564, "lon": 106.6333, "province": "四川省"},
    {"name": "达州", "type": "city", "lat": 31.2090, "lon": 107.4680, "province": "四川省"},
    {"name": "雅安", "type": "city", "lat": 29.9806, "lon": 103.0134, "province": "四川省"},
    {"name": "巴中", "type": "city", "lat": 31.8691, "lon": 106.7478, "province": "四川省"},
    {"name": "资阳", "type": "city", "lat": 30.1288, "lon": 104.6278, "province": "四川省"},
    {"name": "六盘水", "type": "city", "lat": 26.5933, "lon": 104.8305, "province": "贵州省"},
    {"name": "遵义", "type": "city", "lat": 27.7257, "lon": 106.9273, "province": "贵州省"},
    {"name": "安顺", "type": "city", "lat": 26.2455, "lon": 105.9323, "province": "贵州省"},
    {"name": "毕节", "type": "city", "lat": 27.3020, "lon": 105.2841, "province": "贵州省"},
    {"name": "铜仁", "type": "city", "lat": 27.7312, "lon": 109.1896, "province": "贵州省"},
    {"name": "曲靖", "type": "city", "lat": 25.4895, "lon": 103.7961, "province": "云南省"},
    {"name": "玉溪", "type": "city", "lat": 24.3520, "lon": 102.5467, "province": "云南省"},
    {"name": "保山", "type": "city", "lat": 25.1205, "lon": 99.1619, "province": "云南省"},
    {"name": "昭通", "type": "city", "lat": 27.3380, "lon": 103.7173, "province": "云南省"},
    {"name": "丽江", "type": "city", "lat": 26.8558, "lon": 100.2270, "province": "云南省"},
    {"name": "普洱", "type": "city", "lat": 22.8250, "lon": 100.9660, "province": "云南省"},
    {"name": "临沧", "type": "city", "lat": 23.8864, "lon": 100.0927, "province": "云南省"},
    {"name": "宝鸡", "type": "city", "lat": 34.3616, "lon": 107.2379, "province": "陕西省"},
    {"name": "咸阳", "type": "city", "lat": 34.3456, "lon": 108.7091, "province": "陕西省"},
    {"name": "铜川", "type": "city", "lat": 34.8965, "lon": 108.9454, "province": "陕西省"},
    {"name": "渭南", "type": "city", "lat": 34.5024, "lon": 109.5099, "province": "陕西省"},
    {"name": "延安", "type": "city", "lat": 36.5853, "lon": 109.4898, "province": "陕西省"},
    {"name": "汉中", "type": "city", "lat": 33.0674, "lon": 107.0230, "province": "陕西省"},
    {"name": "榆林", "type": "city", "lat": 38.2679, "lon": 109.7341, "province": "陕西省"},
    {"name": "安康", "type": "city", "lat": 32.6850, "lon": 109.0293, "province": "陕西省"},
    {"name": "商洛", "type": "city", "lat": 33.8680, "lon": 109.9402, "province": "陕西省"},
    {"name": "嘉峪关", "type": "city", "lat": 39.7725, "lon": 98.2873, "province": "甘肃省"},
    {"name": "金昌", "type": "city", "lat": 38.5205, "lon": 102.1879, "province": "甘肃省"},
    {"name": "白银", "type": "city", "lat": 36.5448, "lon": 104.1389, "province": "甘肃省"},
    {"name": "天水", "type": "city", "lat": 34.5808, "lon": 105.7244, "province": "甘肃省"},
    {"name": "武威", "type": "city", "lat": 37.9283, "lon": 102.6371, "province": "甘肃省"},
    {"name": "张掖", "type": "city", "lat": 38.9259, "lon": 100.4496, "province": "甘肃省"},
    {"name": "平凉", "type": "city", "lat": 35.5430, "lon": 106.6654, "province": "甘肃省"},
    {"name": "酒泉", "type": "city", "lat": 39.7238, "lon": 98.4941, "province": "甘肃省"},
    {"name": "庆阳", "type": "city", "lat": 35.7094, "lon": 107.6432, "province": "甘肃省"},
    {"name": "定西", "type": "city", "lat": 35.5806, "lon": 104.5861, "province": "甘肃省"},
    {"name": "陇南", "type": "city", "lat": 33.4007, "lon": 104.9211, "province": "甘肃省"},
    {"name": "唐山", "type": "city", "lat": 39.6291, "lon": 118.1802, "province": "河北省"},
    {"name": "秦皇岛", "type": "city", "lat": 39.9354, "lon": 119.5996, "province": "河北省"},
    {"name": "邯郸", "type": "city", "lat": 36.6256, "lon": 114.5391, "province": "河北省"},
    {"name": "保定", "type": "city", "lat": 38.8738, "lon": 115.4648, "province": "河北省"},
    {"name": "张家口", "type": "city", "lat": 40.7677, "lon": 114.8869, "province": "河北省"},
    {"name": "承德", "type": "city", "lat": 40.9511, "lon": 117.9636, "province": "河北省"},
    {"name": "廊坊", "type": "city", "lat": 39.5380, "lon": 116.6831, "province": "河北省"},
    {"name": "衡水", "type": "city", "lat": 37.7348, "lon": 115.6700, "province": "河北省"},
    {"name": "沧州", "type": "city", "lat": 38.3037, "lon": 116.8388, "province": "河北省"},
    {"name": "邢台", "type": "city", "lat": 37.0682, "lon": 114.5042, "province": "河北省"},
    {"name": "洛阳", "type": "city", "lat": 34.6197, "lon": 112.4540, "province": "河南省"},
    {"name": "开封", "type": "city", "lat": 34.7971, "lon": 114.3075, "province": "河南省"},
    {"name": "南阳", "type": "city", "lat": 33.0039, "lon": 112.5286, "province": "河南省"},
    {"name": "安阳", "type": "city", "lat": 36.0979, "lon": 114.3927, "province": "河南省"},
    {"name": "新乡", "type": "city", "lat": 35.3029, "lon": 113.9268, "province": "河南省"},
    {"name": "焦作", "type": "city", "lat": 35.2159, "lon": 113.2420, "province": "河南省"},
    {"name": "濮阳", "type": "city", "lat": 35.7625, "lon": 115.0296, "province": "河南省"},
    {"name": "许昌", "type": "city", "lat": 34.0357, "lon": 113.8523, "province": "河南省"},
    {"name": "漯河", "type": "city", "lat": 33.5818, "lon": 114.0167, "province": "河南省"},
    {"name": "三门峡", "type": "city", "lat": 34.7733, "lon": 111.1941, "province": "河南省"},
    {"name": "商丘", "type": "city", "lat": 34.4144, "lon": 115.6506, "province": "河南省"},
    {"name": "周口", "type": "city", "lat": 33.6264, "lon": 114.6965, "province": "河南省"},
    {"name": "驻马店", "type": "city", "lat": 33.0114, "lon": 114.0222, "province": "河南省"},
    {"name": "信阳", "type": "city", "lat": 32.1285, "lon": 114.0913, "province": "河南省"},
    {"name": "宜昌", "type": "city", "lat": 30.6918, "lon": 111.2867, "province": "湖北省"},
    {"name": "襄阳", "type": "city", "lat": 32.0090, "lon": 112.1222, "province": "湖北省"},
    {"name": "荆州", "type": "city", "lat": 30.3352, "lon": 112.2410, "province": "湖北省"},
    {"name": "黄冈", "type": "city", "lat": 30.4461, "lon": 114.8720, "province": "湖北省"},
    {"name": "孝感", "type": "city", "lat": 30.9243, "lon": 113.9169, "province": "湖北省"},
    {"name": "株洲", "type": "city", "lat": 27.8274, "lon": 113.1337, "province": "湖南省"},
    {"name": "湘潭", "type": "city", "lat": 27.8298, "lon": 112.9447, "province": "湖南省"},
    {"name": "衡阳", "type": "city", "lat": 26.8968, "lon": 112.5717, "province": "湖南省"},
    {"name": "邵阳", "type": "city", "lat": 27.2368, "lon": 111.4672, "province": "湖南省"},
    {"name": "岳阳", "type": "city", "lat": 29.3572, "lon": 113.0963, "province": "湖南省"},
    {"name": "常德", "type": "city", "lat": 29.0318, "lon": 111.6983, "province": "湖南省"},
    {"name": "张家界", "type": "city", "lat": 29.1170, "lon": 110.4793, "province": "湖南省"},
    {"name": "益阳", "type": "city", "lat": 28.5539, "lon": 112.3550, "province": "湖南省"},
    {"name": "郴州", "type": "city", "lat": 25.7705, "lon": 113.0149, "province": "湖南省"},
    {"name": "永州", "type": "city", "lat": 26.4205, "lon": 111.6132, "province": "湖南省"},
    {"name": "怀化", "type": "city", "lat": 27.5500, "lon": 109.9981, "province": "湖南省"},
    {"name": "娄底", "type": "city", "lat": 27.7001, "lon": 111.9939, "province": "湖南省"},
    {"name": "湘西", "type": "city", "lat": 28.3117, "lon": 109.7399, "province": "湖南省"},
]

# 主要河流（20+）
RIVERS = [
    {"name": "长江", "type": "river", "length": 6300, "origin": "青藏高原", "mouth": "东海"},
    {"name": "黄河", "type": "river", "length": 5464, "origin": "巴颜喀拉山", "mouth": "渤海"},
    {"name": "珠江", "type": "river", "length": 2320, "origin": "云贵高原", "mouth": "南海"},
    {"name": "淮河", "type": "river", "length": 1000, "origin": "河南桐柏山", "mouth": "洪泽湖"},
    {"name": "海河", "type": "river", "length": 1050, "origin": "太行山", "mouth": "渤海"},
    {"name": "辽河", "type": "river", "length": 1430, "origin": "河北", "mouth": "渤海"},
    {"name": "松花江", "type": "river", "length": 1927, "origin": "长白山", "mouth": "黑龙江"},
    {"name": "雅鲁藏布江", "type": "river", "length": 2057, "origin": "喜马拉雅山", "mouth": "孟加拉湾"},
    {"name": "怒江", "type": "river", "length": 2013, "origin": "青藏高原", "mouth": "安达曼海"},
    {"name": "澜沧江", "type": "river", "length": 4900, "origin": "青藏高原", "mouth": "南海"},
    {"name": "汉江", "type": "river", "length": 1577, "origin": "陕西", "mouth": "长江"},
    {"name": "湘江", "type": "river", "length": 844, "origin": "广西", "mouth": "洞庭湖"},
    {"name": "赣江", "type": "river", "length": 991, "origin": "江西", "mouth": "鄱阳湖"},
    {"name": "嘉陵江", "type": "river", "length": 1120, "origin": "陕西", "mouth": "长江"},
    {"name": "乌江", "type": "river", "length": 1030, "origin": "贵州", "mouth": "长江"},
    {"name": "岷江", "type": "river", "length": 735, "origin": "四川", "mouth": "长江"},
    {"name": "闽江", "type": "river", "length": 577, "origin": "福建", "mouth": "东海"},
    {"name": "韩江", "type": "river", "length": 470, "origin": "广东", "mouth": "南海"},
    {"name": "钱塘江", "type": "river", "length": 605, "origin": "安徽", "mouth": "杭州湾"},
    {"name": "鸭绿江", "type": "river", "length": 795, "origin": "长白山", "mouth": "黄海"},
    {"name": "图们江", "type": "river", "length": 505, "origin": "长白山", "mouth": "日本海"},
    {"name": "乌苏里江", "type": "river", "length": 890, "origin": "俄罗斯", "mouth": "黑龙江"},
    {"name": "额尔古纳河", "type": "river", "length": 1620, "origin": "内蒙古", "mouth": "黑龙江"},
    {"name": "嫩江", "type": "river", "length": 1370, "origin": "内蒙古", "mouth": "松花江"},
    {"name": "沅江", "type": "river", "length": 1033, "origin": "贵州", "mouth": "洞庭湖"},
    {"name": "资水", "type": "river", "length": 653, "origin": "广西", "mouth": "洞庭湖"},
    {"name": "澧水", "type": "river", "length": 388, "origin": "湖南", "mouth": "洞庭湖"},
]

# 主要山脉（15+）
MOUNTAINS = [
    {"name": "喜马拉雅山脉", "type": "mountain_range", "highest_peak": "珠穆朗玛峰", "elevation": 8848},
    {"name": "昆仑山脉", "type": "mountain_range", "highest_peak": "公格尔山", "elevation": 7649},
    {"name": "天山山脉", "type": "mountain_range", "highest_peak": "托木尔峰", "elevation": 7443},
    {"name": "秦岭", "type": "mountain_range", "highest_peak": "太白山", "elevation": 3771},
    {"name": "大兴安岭", "type": "mountain_range", "highest_peak": "黄岗梁", "elevation": 2029},
    {"name": "太行山脉", "type": "mountain_range", "highest_peak": "小五台山", "elevation": 2882},
    {"name": "武夷山脉", "type": "mountain_range", "highest_peak": "黄岗山", "elevation": 2158},
    {"name": "南岭", "type": "mountain_range", "highest_peak": "猫儿山", "elevation": 2142},
    {"name": "横断山脉", "type": "mountain_range", "highest_peak": "贡嘎山", "elevation": 7556},
    {"name": "阿尔泰山脉", "type": "mountain_range", "highest_peak": "友谊峰", "elevation": 4374},
    {"name": "祁连山脉", "type": "mountain_range", "highest_peak": "团结峰", "elevation": 5808},
    {"name": "阴山山脉", "type": "mountain_range", "highest_peak": "呼和巴什格", "elevation": 2364},
    {"name": "长白山脉", "type": "mountain_range", "highest_peak": "白头山", "elevation": 2691},
    {"name": "云岭", "type": "mountain_range", "highest_peak": "玉龙雪山", "elevation": 5596},
    {"name": "雪峰山", "type": "mountain_range", "highest_peak": "苏宝顶", "elevation": 1934},
]

# 主要湖泊（15+）
LAKES = [
    {"name": "青海湖", "type": "lake", "area": 4583, "province": "青海省", "elevation": 3196},
    {"name": "鄱阳湖", "type": "lake", "area": 3150, "province": "江西省", "elevation": 12},
    {"name": "洞庭湖", "type": "lake", "area": 2625, "province": "湖南省", "elevation": 33},
    {"name": "太湖", "type": "lake", "area": 2250, "province": "江苏省", "elevation": 3},
    {"name": "呼伦湖", "type": "lake", "area": 2339, "province": "内蒙古自治区", "elevation": 545},
    {"name": "纳木错", "type": "lake", "area": 1920, "province": "西藏自治区", "elevation": 4718},
    {"name": "色林错", "type": "lake", "area": 1640, "province": "西藏自治区", "elevation": 4530},
    {"name": "博斯腾湖", "type": "lake", "area": 1019, "province": "新疆维吾尔自治区", "elevation": 1048},
    {"name": "洪泽湖", "type": "lake", "area": 1851, "province": "江苏省", "elevation": 12},
    {"name": "巢湖", "type": "lake", "area": 770, "province": "安徽省", "elevation": 8},
    {"name": "微山湖", "type": "lake", "area": 664, "province": "山东省", "elevation": 34},
    {"name": "滇池", "type": "lake", "area": 330, "province": "云南省", "elevation": 1886},
    {"name": "洱海", "type": "lake", "area": 256, "province": "云南省", "elevation": 1972},
    {"name": "抚仙湖", "type": "lake", "area": 217, "province": "云南省", "elevation": 1721},
    {"name": "西湖", "type": "lake", "area": 6.5, "province": "浙江省", "elevation": 4},
]


class EntityDatabase:
    """地理实体数据库"""

    def __init__(self):
        """初始化实体数据库"""
        self.entities = {
            "provinces": PROVINCES,
            "cities": CITIES,
            "rivers": RIVERS,
            "mountains": MOUNTAINS,
            "lakes": LAKES
        }

    def get_all_entities(self) -> List[Dict[str, Any]]:
        """获取所有实体"""
        all_entities = []
        for entity_type, entities in self.entities.items():
            for entity in entities:
                entity["category"] = entity_type
                all_entities.append(entity)
        return all_entities

    def get_entities_by_type(self, entity_type: str) -> List[Dict[str, Any]]:
        """按类型获取实体"""
        return self.entities.get(entity_type, [])

    def get_entities_with_coords(self) -> List[Dict[str, Any]]:
        """获取有坐标的实体（用于生成方向/度量关系）"""
        entities_with_coords = []
        for entity_type in ["provinces", "cities"]:
            entities_with_coords.extend(self.entities[entity_type])
        return entities_with_coords

    def get_entity_by_name(self, name: str) -> Dict[str, Any]:
        """按名称查找实体"""
        for entity_type, entities in self.entities.items():
            for entity in entities:
                if entity["name"] == name:
                    return entity
        return None

    def random_pair(self, entity_type: str = None) -> tuple:
        """随机选择一对实体"""
        import random

        if entity_type:
            entities = self.get_entities_by_type(entity_type)
        else:
            entities = self.get_all_entities()

        return random.sample(entities, 2)

    def statistics(self) -> Dict[str, int]:
        """返回数据库统计信息"""
        return {
            entity_type: len(entities)
            for entity_type, entities in self.entities.items()
        }

    def save_to_file(self, output_path: str):
        """保存数据库到文件"""
        import os
        all_entities = self.get_all_entities()
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(all_entities, f, indent=2, ensure_ascii=False)
        print(f"[OK] Entity database saved to: {output_path}")

    @classmethod
    def load_from_file(cls, input_path: str) -> 'EntityDatabase':
        """从文件加载数据库"""
        with open(input_path, 'r', encoding='utf-8') as f:
            entities = json.load(f)

        db = cls()
        # 重新分类
        for entity in entities:
            category = entity.pop("category", None)
            if category and category in db.entities:
                db.entities[category].append(entity)

        return db


if __name__ == "__main__":
    import os

    # 创建数据库
    db = EntityDatabase()

    # 打印统计信息
    print("="*60)
    print("地理实体数据库统计")
    print("="*60)
    stats = db.statistics()
    total_entities = sum(stats.values())
    for entity_type, count in stats.items():
        print(f"{entity_type:20s}: {count:5d} 个")
    print(f"{'='*60}")
    print(f"{'总计':20s}: {total_entities:5d} 个实体")
    print("="*60)

    # 保存到文件
    output_dir = "D:/30_keyan/GeoKD-SR/data/geosr_chain"
    os.makedirs(output_dir, exist_ok=True)
    db.save_to_file(f"{output_dir}/entity_database.json")

    # 测试随机选择
    print("\n测试随机选择实体对:")
    for i in range(5):
        entity1, entity2 = db.random_pair("cities")
        print(f"{i+1}. {entity1['name']} ({entity1['lat']}°N, {entity1['lon']}°E) "
              f"- {entity2['name']} ({entity2['lat']}°N, {entity2['lon']}°E)")

    print("\n[OK] Geographic entity database built successfully!")
