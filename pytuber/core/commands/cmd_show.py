from typing import Optional

import click
from tabulate import tabulate

from pytuber.core import params
from pytuber.core.models import PlaylistManager, TrackManager


@click.command()
@click.argument("id", type=params.PlaylistParamType())
def show(id: Optional[str]):
    """Show a playlist track list."""

    playlist = PlaylistManager.get(id)
    click.echo_via_pager(
        tabulate(
            [
                (t.artist, t.name, "✔" if t.youtube_id else "-")
                for t in [TrackManager.get(id) for id in playlist.tracks]
            ],
            showindex="always",
            headers=("No", "Artist", "Track Name", "Youtube"),
        )
    )
