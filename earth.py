import matplotlib.pyplot as plt
import cartopy.crs as ccrs

# Создаем фигуру
fig = plt.figure(figsize=(10, 10))

# Выбираем проекцию Orthographic (вид из космоса)
# lat_0, lon_0 — точка, на которую смотрим (центр карты)
ax = fig.add_subplot(1, 1, 1, projection=ccrs.Orthographic(central_longitude=30, central_latitude=45))

# Добавляем береговую линию.
# Аргумент resolution отвечает за детализацию: '110m' (самая грубая), '50m', '10m' (самая детальная)
ax.coastlines(resolution='110m', color='black', linewidth=0.8)

# Добавляем сетку долгот и широт (опционально)
ax.gridlines(draw_labels=False, linestyle='--', alpha=0.5)

# Заливаем океан и сушу для наглядности
ax.add_feature(cartopy.feature.OCEAN, color='lightblue', alpha=0.7)
ax.add_feature(cartopy.feature.LAND, color='whitesmoke', alpha=0.5)

plt.title("Вид на Землю из космоса (Orthographic)")
plt.show()

