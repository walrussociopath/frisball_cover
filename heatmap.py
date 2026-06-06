import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.io.shapereader as shpreader

# Ваши данные по регионам: название региона -> значение для heatmap
# Важно: названия должны точно совпадать с атрибутом 'name' в shapefile
region_values = {
    'Moscow': 100,
    'Sankt-Peterburg': 85,
    'Moskovskaya': 70,
    # ... добавьте остальные регионы
}

# Загружаем границы регионов РФ (административный уровень 1)
# Используем масштаб '50m' для баланса детализации и производительности
shpfilename = shpreader.natural_earth(
    resolution='50m',
    category='cultural',
    name='admin_1_states_provinces'
)

reader = shpreader.Reader(shpfilename)

# Собираем геометрии и значения для закраски
geometries = []
values = []

for record in reader.records():
    # Фильтруем только регионы РФ (country_code = 'RU')
    if record.attributes.get('admin') == 'Russia' or record.attributes.get('iso_3166_2', '').startswith('RU-'):
        region_name = record.attributes.get('name')
        geometries.append(record.geometry)
        # Берем значение из словаря, если нет — 0 или None (прозрачный)
        values.append(region_values.get(region_name, 0))

# Создаем карту
fig = plt.figure(figsize=(12, 8))
ax = fig.add_subplot(projection=ccrs.PlateCarree())

# Ограничиваем область видимости РФ
ax.set_extent([20, 190, 40, 82], crs=ccrs.PlateCarree())

# Добавляем контуры материков для контекста
ax.coastlines(resolution='50m', linewidth=0.5)

# Рисуем хороплет
art = ax.add_geometries(
    geometries,
    crs=ccrs.PlateCarree(),
    array=values,
    cmap='Reds',           # цветовая схема (Reds, YlOrRd, plasma)
    edgecolor='black',
    linewidth=0.5,
    alpha=0.8
)

# Добавляем цветовую шкалу
cbar = fig.colorbar(art, orientation='horizontal', pad=0.05)
cbar.set_label('Значение параметра')

plt.title('Heatmap регионов РФ')
plt.show()