import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature

# Создаем проекцию "вид на шар" (ортографическая)
fig, ax = plt.subplots(figsize=(10, 10),
                       subplot_kw={'projection': ccrs.NearsidePerspective(
                           central_longitude=18, central_latitude=40,
                           satellite_height=2000000
                       )})

# --- Магия здесь: добавляем готовые географические объекты ---
# Заливаем океан (он будет фоном)
ax.add_feature(cfeature.OCEAN, facecolor='lightblue')
# Добавляем контуры материков
ax.add_feature(cfeature.COASTLINE, linewidth=0.8)
# Заливаем сушу (опционально, для наглядности)
ax.add_feature(cfeature.LAND, facecolor='lightgray', alpha=0.7)

# Показываем весь глобус
ax.set_global()
ax.gridlines()

plt.title("Контуры материков на глобусе")
plt.show()