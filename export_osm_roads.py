"""
将PostGIS中的osm_roads表导出为Shapefile格式(.shp)
使用pyogrio(GDAL)直接读写，避免psycopg2在中文Windows下的编码问题
"""
import os
import pyogrio

# 数据库连接参数
DB_HOST = 'localhost'
DB_PORT = '5432'
DB_NAME = 'postgres'
DB_USER = 'postgres'
DB_PASS = 'postgres'

# 输出路径
OUTPUT_DIR = r'D:\30_keyan\output'
OUTPUT_SHP = os.path.join(OUTPUT_DIR, 'osm_roads.shp')

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 构建GDAL PostGIS连接字符串
    pg_str = (
        f"PG:host={DB_HOST} port={DB_PORT} dbname={DB_NAME} "
        f"user={DB_USER} password={DB_PASS}"
    )

    print("正在从PostGIS读取osm_roads表...")
    print(f"连接: {pg_str}")

    # 使用pyogrio从PostGIS读取
    gdf = pyogrio.read_dataframe(
        pg_str,
        layer='osm_roads'
    )

    print(f"读取完成，共 {len(gdf)} 条记录")
    print(f"字段: {list(gdf.columns)}")
    print(f"坐标系: {gdf.crs}")
    if hasattr(gdf, 'geom_type'):
        print(f"几何类型: {gdf.geom_type.unique()}")

    # 导出到Shapefile
    print(f"\n正在导出Shapefile...")
    pyogrio.write_dataframe(gdf, OUTPUT_SHP, encoding='UTF-8')

    print(f"\n导出成功！文件保存在: {OUTPUT_SHP}")
    print(f"包含文件:")
    for ext in ['.shp', '.shx', '.dbf', '.prj', '.cpg']:
        f = OUTPUT_SHP.replace('.shp', ext)
        if os.path.exists(f):
            size = os.path.getsize(f) / 1024 / 1024
            print(f"  {os.path.basename(f)}: {size:.2f} MB")

    print(f"\n可以在QGIS中直接打开 {OUTPUT_SHP} 进行可视化展示")

if __name__ == "__main__":
    main()
