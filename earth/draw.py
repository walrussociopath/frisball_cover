import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature


def draw(
    lat: float,
    long: float, 

    height: float = 2_000_000,
    filename: str | None = None,
) -> None:
    """
    lat: Широта
    long: Долгота 
    
    height: Высота над землей
    filename: Название файла
    """
    fig, ax = plt.subplots(
        figsize=(10, 10),
        subplot_kw={
            'projection': ccrs.NearsidePerspective(
                            central_longitude=long, 
                            central_latitude=lat,
                            satellite_height=2_000_000
                        )
        }
    )
    ax.add_feature(cfeature.COASTLINE, linewidth=0.8, color='black')
    ax.add_feature(cfeature.LAND, facecolor='lightgray', alpha=0.7)
    ax.set_global()

    plt.savefig(
        f'images/globe_{long}_{lat}_{height}.png' if filename is None else filename, 
        dpi=300, 
        transparent=True,
        bbox_inches='tight',
    )
