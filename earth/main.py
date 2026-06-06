import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import numpy as np


def draw(long, lat):
    fig, ax = plt.subplots(figsize=(10, 10),
                        subplot_kw={'projection': ccrs.NearsidePerspective(
                            central_longitude=long, central_latitude=lat,
                            satellite_height=2000000
                        )})

    # Добавляем контуры материков
    ax.add_feature(cfeature.COASTLINE, linewidth=0.8, color='black')

    # Заливаем сушу
    ax.add_feature(cfeature.LAND, facecolor='lightgray', alpha=0.7)

    # Показываем весь глобус
    ax.set_global()

    # Сохраняем с прозрачным фоном и без сетки
    plt.savefig(f'globe_nudes/{long}_{lat}.png', 
                dpi=300, 
                transparent=True,      # Файл PNG с прозрачностью
                bbox_inches='tight',
                facecolor='none')


if __name__ == '__main__':
    draw(25, 42)
