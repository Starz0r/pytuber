from unittest import mock

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from pytuber.exceptions import NotFound
from pytuber.models import ConfigManager
from pytuber.youtube.models import PlaylistItem
from pytuber.youtube.services import YouService
from tests.utils import PlaylistFixture, TestCase, TrackFixture


class YouServiceTests(TestCase):
    def setUp(self):
        super(YouServiceTests, self).setUp()
        YouService.max_results = 2

    def tearDown(self):
        YouService.max_results = 50
        super(YouServiceTests, self).tearDown()

    @mock.patch.object(InstalledAppFlow, "from_client_secrets_file")
    def test_authorize(self, from_secrets):
        path = "~/Downloads/client_secets.json"
        from_secrets.return_value.run_console.return_value = "foo"

        self.assertEqual("foo", YouService.authorize(path))
        from_secrets.assert_called_once_with(path, scopes=YouService.scopes)

    @mock.patch.object(YouService, "get_client")
    def test_search(self, get_client):
        list = get_client.return_value.search.return_value.list
        list.return_value.execute.return_value = {
            "items": [{"id": {"kind": "youtube#video", "videoId": "101"}}]
        }

        track = TrackFixture.one()
        self.assertEqual("101", YouService.search_track(track))
        list.assert_called_once_with(
            part="snippet",
            maxResults=1,
            q="{} {}".format(track.artist, track.name),
            type="video",
        )

    @mock.patch.object(YouService, "get_client")
    def test_get_playlists(self, get_client):
        playlist = PlaylistFixture.one()
        list = get_client.return_value.playlists.return_value.list
        list.return_value.execute.side_effect = [
            {
                "nextPageToken": 2,
                "items": [
                    {
                        "id": "a",
                        "snippet": {
                            "description": playlist.mime,
                            "title": "One",
                        },
                    },
                    {"snippet": {"description": "", "title": ""}},
                ],
            },
            {"items": [{"snippet": {"description": "", "title": ""}}]},
        ]

        actual = YouService.get_playlists()
        self.assertEqual(1, len(actual))
        self.assertEqual("One", actual[0].title)
        list.assert_has_calls(
            [
                mock.call(part="snippet", mine=True, maxResults=2),
                mock.call().execute(),
                mock.call(
                    part="snippet", mine=True, maxResults=2, pageToken=2
                ),
                mock.call().execute(),
            ]
        )

    @mock.patch.object(YouService, "get_client")
    def test_create_playlist(self, get_client):
        playlist = PlaylistFixture.one()
        insert = get_client.return_value.playlists.return_value.insert
        insert.return_value.execute.return_value = {"id": "101"}

        self.assertEqual("101", YouService.create_playlist(playlist))
        insert.assert_called_once_with(
            body=dict(
                snippet=dict(
                    title=playlist.display_type, description=playlist.mime
                ),
                status=dict(privacyStatus="private"),
            ),
            part="snippet,status",
        )

    @mock.patch.object(YouService, "get_client")
    def test_get_playlist_items(self, get_client):
        playlist = PlaylistFixture.one()
        list = get_client.return_value.playlistItems.return_value.list
        list.return_value.execute.side_effect = [
            {
                "nextPageToken": 3,
                "items": [
                    {"id": "a", "contentDetails": {"videoId": "va"}},
                    {"id": "b", "contentDetails": {"videoId": "vb"}},
                ],
            },
            {"items": [{"id": "c", "contentDetails": {"videoId": "vc"}}]},
        ]

        actual = YouService.get_playlist_items(playlist)
        self.assertEqual(3, len(actual))
        self.assertEqual("a", actual[0].id)
        self.assertEqual("va", actual[0].video_id)
        self.assertEqual("b", actual[1].id)
        self.assertEqual("vb", actual[1].video_id)
        self.assertEqual("c", actual[2].id)
        self.assertEqual("vc", actual[2].video_id)

        list.assert_has_calls(
            [
                mock.call(
                    part="contentDetails",
                    maxResults=2,
                    playlistId=playlist.youtube_id,
                ),
                mock.call().execute(),
                mock.call(
                    part="contentDetails",
                    maxResults=2,
                    playlistId=playlist.youtube_id,
                    pageToken=3,
                ),
                mock.call().execute(),
            ]
        )

    @mock.patch.object(YouService, "get_client")
    def test_create_playlist_item(self, get_client):
        playlist = PlaylistFixture.one(youtube_id="b")
        insert = get_client.return_value.playlistItems.return_value.insert
        insert.return_value.execute.return_value = "foo"

        self.assertEqual(
            "foo", YouService.create_playlist_item(playlist, "aa")
        )
        insert.assert_called_once_with(
            body=dict(
                snippet=dict(
                    playlistId=playlist.youtube_id,
                    resourceId=dict(kind="youtube#video", videoId="aa"),
                )
            ),
            part="snippet",
        )

    @mock.patch.object(YouService, "get_client")
    def test_remove_playlist_item(self, get_client):
        item = PlaylistItem(id="a", video_id="b")
        delete = get_client.return_value.playlistItems.return_value.delete
        delete.return_value.execute.return_value = "foo"

        self.assertEqual("foo", YouService.remove_playlist_item(item))
        delete.assert_called_once_with(id=item.id)

    @mock.patch("pytuber.youtube.services.build")
    @mock.patch.object(Credentials, "from_authorized_user_info")
    def test_get_client(self, get_user_info, build):
        with self.assertRaises(NotFound):
            YouService.get_client()

        ConfigManager.set(data=dict(provider="youtube", data="foo"))
        get_user_info.return_value = "creds"
        build.return_value = "client"

        actual = YouService.get_client()
        self.assertEqual("client", actual)

        get_user_info.assert_called_once_with("foo", scopes=YouService.scopes)
        build.assert_called_once_with("youtube", "v3", credentials="creds")