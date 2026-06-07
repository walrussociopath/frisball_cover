from typing import Collection, Generator, Literal
import logging
from uuid import uuid4

import cartopy.io.shapereader as shapereader
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import numpy as np
from shapely import contains_xy
from shapely.geometry import Point
from shapely.ops import unary_union

import json
from shapely.geometry import mapping
from shapely.ops import unary_union

from utils import elapse_time, in_thread


#  Формат города  name lat    lon    radius
type City = tuple[str, float, float, float]




def gauss_heat(r: float, dist: float):
    # Каждый город создает пятно МАКСИМАЛЬНОЙ интенсивности (1.0)
    influence = np.exp(-dist**2 / (2 * r**2))
    return influence


def exp_heat(r, dist):
    scale = r * 12.0  # Длинный хвост (чем больше, тем длиннее)
    # Лапласовское распределение (экспоненциальное)
    influence = np.exp(-np.abs(dist) / scale)
    return influence


def add_circular_noise(influence, amplitude=0.1, frequency=20):
    """Добавляет шум, нарушающий круговую симметрию"""
    rows, cols = influence.shape
    
    # Угловой шум (нарушает круговую симметрию)
    theta = np.random.rand(rows, cols) * 2 * np.pi
    angular_noise = amplitude * np.sin(frequency * theta)
    
    # Радиальный шум
    radial_noise = amplitude * np.random.randn(rows, cols) * 0.5
    
    return influence * (1 + angular_noise + radial_noise)


def add_fractal_background(influence, intensity=0.007, octaves=2):
    """Добавляет фрактальный шум на фон"""
    rows, cols = influence.shape
    
    noise = np.zeros((rows, cols))
    
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
    
    # Добавляем случайную составляющую
    noise += np.random.randn(rows, cols) * intensity * 0.2
    
    return influence + np.abs(noise)


class Drawer:
    def __init__(
        self, 
        cities: Collection[City], 
        regions: Collection[str],
        #                                              lat  lat lon lon
        view_zone: tuple[float, float, float, float] = (25, 50, 40, 70),
        grid_resolution: int = 1000,
        base_heat: float = 0.04,
        cumulativity: float = 0.6,
        r_coef: float = 0.1,
        alg: Literal['gauss', 'exp'] = 'exp',
    ):
        """
        cities: Города в формате (Название, широта, долгота, коэффициент интенсивности радиуса)
        regions: Названия регионов 
        view_zone: Диапазон отображения карты по долготам и широтам
        grid_resolution: Сколько точек используется в сетке (Чем больше, тем плавнее картинка)
        base_heat: Теплота минимальных участков
        cumulativity: Насколько сильно сливается теплота соседних городов
        r_coef: Управление радиусом очагов городов 
        alg: Алгоритм построения очагов
        """
        self._cities = cities
        self._unpack_cities()
        
        self._region_names = regions
        self._regions_shapes = set(find_regions_records(regions))
        self._view_zone = view_zone
        self._resolution = grid_resolution
        self._base_heat = base_heat
        self._cumulativity = cumulativity
        self._r_coef = r_coef
        self._alg = alg

        # Канвас
        self.fig, self.ax = plt.subplots(
            figsize=(20, 20),
            subplot_kw={'projection': ccrs.PlateCarree()}
        )

        self.res = 1000

    def _unpack_cities(self):
        self._lats = np.array([city[1] for city in self._cities])
        self._lons = np.array([city[2] for city in self._cities])
        self._coeffs = np.array([city[3] for city in self._cities])

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
        self.ax.scatter(self._lons, self._lats,
            transform=ccrs.PlateCarree(),
            s=20,
            color='blue',
            alpha=0.8,
            edgecolor='white',
            linewidth=0.5,
            zorder=5
        )

    def draw_union_regions(self) -> None:
        """Для тестов."""
        union_regions = UnionRegions(
            regions=self._region_names, region_records=self._regions_shapes
        ).geometry
        
        # Отрисовываем заливку
        self.ax.add_geometries(
            [union_regions],
            crs=ccrs.PlateCarree(),
            edgecolor='red',      # Контур красный
            facecolor='lightblue', # Заливка голубая
            alpha=0.5,            # Полупрозрачная
            linewidth=2           # Толстая линия
        )
        
        self.set_canvas_options()
        plt.show()

    def _draw_heatmap(self, apply_region_mask: bool = True):
        lon_grid, lat_grid = self._create_grid()
        heat = np.zeros(lon_grid.shape)

        with elapse_time('Calculation heat'):
            for name, lon, lat, r in zip(self._cities, self._lons, self._lats, self._coeffs):
                # Расстояние до каждой точки сетки
                dist = np.sqrt((lon_grid - lon)**2 + (lat_grid - lat)**2)
                # Радиус влияния (фиксированный для всех)
                influence = self._get_influence(r * self._r_coef, dist) 
                
                influence = add_circular_noise(influence)
                influence = add_fractal_background(influence)
                heat = (1 - self._cumulativity) * np.maximum(heat, influence) + self._cumulativity * (heat + influence)
                # Ограничиваем максимум 1
                heat = self._base_heat + (1 - self._base_heat) * np.minimum(heat, 1)

        if apply_region_mask:
            heat = self._apply_region_mask(heat)
        
        heatmap = self.ax.pcolormesh(lon_grid, lat_grid, heat,
                        transform=ccrs.PlateCarree(),
                        cmap='hot', alpha=0.7, shading='auto',
                        vmin=0, vmax=1)    

    def _get_influence(self, r: float, dist):
        if self._alg == 'gauss':
            return gauss_heat(r, dist)
        if self._alg == 'exp':
            return exp_heat(r, dist)

    def _apply_region_mask(self, heat): 
        combined_regions = unary_union([record.geometry for record in self._regions_shapes])
        lon_grid, lat_grid = self._create_grid() 

        with elapse_time('Apply mask'):
            region_mask = np.zeros(lon_grid.shape, dtype=bool)
            region_mask = contains_xy(combined_regions, lon_grid, lat_grid)
    
        return np.where(region_mask, heat, 0)
    
    def _create_grid(self):
        lon_grid = np.linspace(self._view_zone[0], self._view_zone[1], self._resolution)
        lat_grid = np.linspace(self._view_zone[2], self._view_zone[3], self._resolution)
        lon_grid, lat_grid = np.meshgrid(lon_grid, lat_grid)
        return lon_grid, lat_grid
    
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

    def save(self):
        self.fig.savefig(f'{uuid4()}.png', dpi=300, bbox_inches='tight', facecolor='white')
    

shp = shapereader.natural_earth(resolution='50m', category='cultural', name='admin_1_states_provinces')
reader = shapereader.Reader(shp)


def find_regions_records(region_names: Collection[str]) -> Generator[shapereader.Record]:
    names_founded = set()
    for record in reader.records():
        if (region_name := record.attributes.get('name_ru')) in region_names:
            names_founded.add(region_name)
            yield record
    if len(names_founded) != len(region_names):
        not_found_regions = set(region_names) - names_founded
        raise KeyError(f'Regions {not_found_regions} not found')


class UnionRegions:
    def __init__(
        self, 
        regions: Collection[str], 
        region_records: Collection[shapereader.Record],
        filename: str = 'combined_regions.geojson',
        use_cache: bool = False,
    ):
        self._regions = regions
        self._filename = filename

        if use_cache and (geometry := self._load_geometry(self._regions, self._filename)):
            self._geometry = geometry
        else:
            self._geometry = self._generate_cache(regions, region_records, filename)

    @property
    def geometry(self):
        return self._geometry

    def _load_geometry(self, regions: Collection[str], filename: str):
        logging.info('Trying to load cache')
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                union_content = json.load(f)
            if self._check_regions(regions, union_content):
                return union_content['features'][0]['geometry']
        except FileNotFoundError:
            logging.info('Cache file not found')
        return None
            
    def _generate_cache(
        self, 
        regions: Collection[str], 
        region_records: Collection[shapereader.Record], 
        filename: str
    ):
        with elapse_time('Building regions union'):
            geometry = unary_union([record.geometry for record in region_records])

        with elapse_time('Saving cache'):
            self._save_geometry(geometry, regions, filename)
        
        return geometry

    def _check_regions(self, regions: Collection[str], union_meta) -> bool:
        """Проверить, что объединение валидное для этих регионов (регионы совпадают)"""

        try:
            cached_regions = union_meta['features'][0]['properties']['regions']
            assert set(cached_regions) == set(regions) 
        except (KeyError, TypeError, IndexError):
            logging.info('Invalid cached geojson format')
        except AssertionError:
            logging.info('Different runtime and cached regions')
        else:
            return True
        return False

    @in_thread
    def _save_geometry(self, geometry, regions: Collection[str], filename: str) -> None:
        """Сохранить файл кэша с объединенными регионами."""

        geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {
                        "name": "Combined Regions",
                        "area": geometry.area,
                        'regions': list(regions),
                    },
                    "geometry": mapping(geometry)
                }
            ]
        }

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(geojson, f, ensure_ascii=False)
            
        logging.info('Regions union cache saved')
