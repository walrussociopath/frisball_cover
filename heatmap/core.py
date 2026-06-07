from dataclasses import dataclass
from typing import Collection, Generator, Literal
from functools import lru_cache
from uuid import uuid4

import cartopy.io.shapereader as shapereader
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import numpy as np
from shapely import contains_xy
from shapely.ops import unary_union

from utils import perf_time


#  Формат города  name lat    lon    radius
type City = tuple[str, float, float, float]


@dataclass(frozen=True)
class HeatConfig:
    # Минимальная жара на карте
    base_heat: float = 0.04
    # Насколько сильно очаги жары сливаются
    cumulativity: float = 0.6
    # Коэффициент радиусу очага. Чтобы не править радиус всех очагов вместе, можно управлять им 
    r_coef: float = 0.1
    # Алгоритм распространения очага
    alg: Literal['gauss', 'exp'] = 'exp'

    # Параметры шума против симметрии очагов
    circular_noise_amplitude: float = 0.1
    circular_noise_frequency: float = 20

    # Интенсивность шума фона
    background_noise_intensity: float = 0.007
    
    # Коэффициент длины распространения ореола очага 
    exp_scale_coef: float = 12


DEFAULT_HEAT_CONFIG = HeatConfig()


class Drawer:
    def __init__(
        self, 
        cities: Collection[City], 
        regions: Collection[str],
        #                                              lat  lat lon lon
        view_zone: tuple[float, float, float, float] = (25, 50, 40, 70),
        fig_size: tuple[int, int] = (20, 20),
        grid_resolution: int = 1000,
        heat_config: HeatConfig = DEFAULT_HEAT_CONFIG,
    ):
        """
        cities: Города в формате (Название, широта, долгота, радиус очага)
        regions: Названия регионов

        view_zone: Диапазон отображения карты по долготам и широтам
        fig_size: Размер канваса, смотреть matplotlib subplots
        grid_resolution: Сколько точек используется в сетке (Чем больше, тем плавнее картинка)
        heat_config: Параметры отрисовки heatmap
        """

        self._cities = cities
        
        self._region_names = regions
        self._regions_shapes = set(find_regions_records(regions))
        self._view_zone = view_zone
        self._resolution = grid_resolution
        self._heat_config = heat_config

        # Канвас
        self.fig, self.ax = plt.subplots(
            figsize=fig_size,
            subplot_kw={'projection': ccrs.PlateCarree()}
        )

    def _draw_regions(self):
        for record in self._regions_shapes:
            geometry = record.geometry
            self.ax.add_geometries(
                [geometry],           #
                crs=ccrs.PlateCarree(),
                edgecolor='black',    
                facecolor='none',     
                linewidth=0.5
            )

    def _draw_cities(self):
        lons, lats, _ = unpack_cities(self._cities)
        self.ax.scatter(lons, lats,
            transform=ccrs.PlateCarree(),
            s=20,
            color='blue',
            alpha=0.8,
            edgecolor='white',
            linewidth=0.5,
            zorder=5
        )

    def draw_union_regions(self) -> None:
        """Для тестов. Посмотреть как выглядят регионы."""

        union_regions = unary_union([record.geometry for record in self._regions_shapes])
        
        # Отрисовываем заливку
        self.ax.add_geometries(
            [union_regions],
            crs=ccrs.PlateCarree(),
            edgecolor='red',
            facecolor='lightblue',
            alpha=0.5,            
            linewidth=2           
        )
        
        self.set_canvas_options()
        plt.show()

    def _draw_heatmap(self, apply_region_mask: bool) -> None:
        heat_drawer = HeatDrawer(
            view_zone=self._view_zone,
            resolution=self._resolution,
            cities=self._cities,
            region_shapes=self._regions_shapes,
            ax=self.ax,
            heat_config=self._heat_config,
        )
        heat_drawer.draw_heatmap(apply_region_mask=apply_region_mask)

    def draw(
        self, 
        add_regions: bool = True, 
        add_cities: bool = True, 
        add_heatmap: bool = True, 
        add_coastline: bool = True, 
        add_gridlines: bool = True,  
        apply_region_mask: bool = True,  
    ):
        if add_regions:
            self._draw_regions()
        if add_cities:
            self._draw_cities()
        if add_heatmap:
            self._draw_heatmap(apply_region_mask=apply_region_mask)

        self.set_canvas_options(
            draw_coastline=add_coastline,
            draw_gridlines=add_gridlines,
        )
        plt.show()

    def set_canvas_options(self, draw_coastline: bool = True, draw_gridlines: bool = True) -> None:
        self.ax.set_extent(self._view_zone, crs=ccrs.PlateCarree())
        if draw_coastline:
            self.ax.coastlines(resolution='110m', color='blue', linewidth=0.5)
        if draw_gridlines:
            self.ax.gridlines(draw_labels=True, dms=True, x_inline=False, y_inline=False)

    def save(self, filename: str | None = None):
        """
        filename: Если не передать, случайный
        """
        if filename is None:
            filename = f'images/{uuid4()}.png'

        self.fig.savefig(filename, dpi=300, bbox_inches='tight', facecolor='white')


class HeatDrawer:
    def __init__(
        self,
        view_zone: tuple[float, float, float, float],
        resolution: int,
        cities: Collection[City],
        region_shapes: Collection[shapereader.Record],
        ax,
        heat_config: HeatConfig = DEFAULT_HEAT_CONFIG,
    ):
        self._ax = ax
        self._view_zone = view_zone
        self._resolution = resolution
        self._heat_config = heat_config
        self._alg = heat_config.alg

        self._lats, self._lons, self._coefs = unpack_cities(cities)
        self._regions_shapes = region_shapes
        
    def draw_heatmap(self, apply_region_mask: bool = True):
        r_coef = self._heat_config.r_coef
        cumulativity = self._heat_config.cumulativity
        base_heat = self._heat_config.base_heat 

        lon_grid, lat_grid = self._create_grid()
        heat = np.zeros(lon_grid.shape)
        
        with perf_time('Calculation heat'):
            for lon, lat, r in zip(self._lons, self._lats, self._coefs):
                dist = np.sqrt((lon_grid - lon)**2 + (lat_grid - lat)**2)
                
                # Влияние очагов
                influence = self._get_influence(r * r_coef, dist) 
                influence = self.add_circular_noise(
                    influence,
                    amplitude=self._heat_config.circular_noise_amplitude,
                    frequency=self._heat_config.circular_noise_frequency,
                )
                influence = self.add_fractal_background(
                    influence,
                    intensity=self._heat_config.background_noise_intensity,
                )

                heat = (1 - cumulativity) * np.maximum(heat, influence) + cumulativity * (heat + influence)
                
                # Ограничение максимума. Иначе центры очагов могут потускнеть
                heat = base_heat + (1 - base_heat) * np.minimum(heat, 1)

        if apply_region_mask:
            heat = self._apply_region_mask(heat)
        
        _ = self._ax.pcolormesh(
            lon_grid, lat_grid, heat,
            transform=ccrs.PlateCarree(),
            cmap='hot', 
            alpha=0.7, 
            shading='auto',
            vmin=0, 
            vmax=1
        )    

    def _apply_region_mask(self, heat): 
        combined_regions = unary_union([record.geometry for record in self._regions_shapes])
        lon_grid, lat_grid = self._create_grid() 

        with perf_time('Apply mask'):
            region_mask = np.zeros(lon_grid.shape, dtype=bool)
            region_mask = contains_xy(combined_regions, lon_grid, lat_grid)
    
        return np.where(region_mask, heat, 0)
    
    def _create_grid(self):
        lon_grid = np.linspace(self._view_zone[0], self._view_zone[1], self._resolution)
        lat_grid = np.linspace(self._view_zone[2], self._view_zone[3], self._resolution)
        lon_grid, lat_grid = np.meshgrid(lon_grid, lat_grid)
        return lon_grid, lat_grid
    
    def _get_influence(self, r, dist):
        if self._alg == 'exp':
            return self.exp_heat(r, dist, self._heat_config.exp_scale_coef)
        if self._alg == 'gauss':
            return self.gauss_heat(r, dist)

    @staticmethod
    def gauss_heat(r: float, dist: float):
        influence = np.exp(-dist**2 / (2 * r**2))
        return influence

    @staticmethod
    def exp_heat(r, dist, scale_coef: float):
        scale = r * scale_coef
        influence = np.exp(-np.abs(dist) / scale)
        return influence
Настройки жары описаны в HeatConfig

    @staticmethod
    def add_circular_noise(influence, amplitude: float = 0.1, frequency: float = 20):
        """Добавляет шум, нарушающий круговую симметрию очагов."""

        rows, cols = influence.shape
        
        # Угловой шум (нарушает круговую симметрию)
        theta = np.random.rand(rows, cols) * 2 * np.pi
        angular_noise = amplitude * np.sin(frequency * theta)
        
        # Радиальный шум
        radial_noise = amplitude * np.random.randn(rows, cols) * 0.5
        
        return influence * (1 + angular_noise + radial_noise)

    @staticmethod
    def add_fractal_background(influence, intensity=0.007):
        """Добавляет фрактальный шум на фон"""
        rows, cols = influence.shape
        
        noise = np.zeros((rows, cols))
        octaves = 2

        for octave in range(octaves):
            freq = 2 ** octave
            amp = intensity / (2 ** octave)
            
            y, x = np.ogrid[:rows, :cols]
            phase_x = x * freq * 2 * np.pi / cols
            phase_y = y * freq * 2 * np.pi / rows
            
            octave_noise = amp * (
                np.sin(phase_x) * np.cos(phase_y) +
                np.sin(phase_x * 1.7) * 0.3
            )
            
            noise += octave_noise

        noise += np.random.randn(rows, cols) * intensity * 0.2
        
        return influence + np.abs(noise)


@lru_cache
def get_cartopy_reader():
    shp = shapereader.natural_earth(resolution='50m', category='cultural', name='admin_1_states_provinces')
    reader = shapereader.Reader(shp)
    return reader


def find_regions_records(region_names: Collection[str]) -> Generator[shapereader.Record]:
    region_names = set(region_names)
    reader = get_cartopy_reader()
    names_found = set()
    for record in reader.records():
        if (region_name := record.attributes.get('name_ru')) in region_names:
            names_found.add(region_name)
            yield record
    if len(names_found) != len(region_names):
        regions_not_found = region_names - names_found
        raise KeyError(f'Regions {regions_not_found} not found')


def unpack_cities(cities: Collection[City]):
    lats = np.array([city[1] for city in cities])
    lons = np.array([city[2] for city in cities])
    coefs = np.array([city[3] for city in cities])
    return lats, lons, coefs
