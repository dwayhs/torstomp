# -*- coding:utf-8 -*-
from unittest import TestCase
import six

from torstomp.protocol import StompProtocol

from mock import MagicMock


class TestRecvFrame(TestCase):

    def setUp(self):
        self.protocol = StompProtocol()

    def test_decode(self):
        self.assertEqual(
            self.protocol._decode(u'éĂ'),
            u'éĂ'
        )

    def test_on_decode_error_show_string(self):
        data = MagicMock(spec=six.binary_type)
        data.decode.side_effect = UnicodeDecodeError(
            'hitchhiker',
            b"",
            42,
            43,
            'the universe and everything else'
        )
        with self.assertRaises(UnicodeDecodeError):
            self.protocol._decode(data)

    def test_single_packet(self):
        self.protocol.add_data(
            b'CONNECT\n'
            b'accept-version:1.0\n\n\x00'
        )

        frames = self.protocol.pop_frames()

        self.assertEqual(len(frames), 1)
        self.assertEqual(frames[0].command, u'CONNECT')
        self.assertEqual(frames[0].headers, {u'accept-version': u'1.0'})
        self.assertEqual(frames[0].body, None)

        self.assertEqual(self.protocol._pending_parts, [])

    def test_parcial_packet(self):
        stream_data = (
            b'CONNECT\n',
            b'accept-version:1.0\n\n\x00',
        )

        for data in stream_data:
            self.protocol.add_data(data)

        frames = self.protocol.pop_frames()

        self.assertEqual(len(frames), 1)
        self.assertEqual(frames[0].command, u'CONNECT')
        self.assertEqual(frames[0].headers, {u'accept-version': u'1.0'})
        self.assertEqual(frames[0].body, None)

    def test_multi_parcial_packet1(self):
        stream_data = (
            b'CONNECT\n',
            b'accept-version:1.0\n\n\x00\n',
            b'CONNECTED\n',
            b'version:1.0\n\n\x00\n'
        )

        for data in stream_data:
            self.protocol.add_data(data)

        frames = self.protocol.pop_frames()
        self.assertEqual(len(frames), 2)

        self.assertEqual(frames[0].command, u'CONNECT')
        self.assertEqual(frames[0].headers, {u'accept-version': u'1.0'})
        self.assertEqual(frames[0].body, None)

        self.assertEqual(frames[1].command, u'CONNECTED')
        self.assertEqual(frames[1].headers, {u'version': u'1.0'})
        self.assertEqual(frames[1].body, None)

        self.assertEqual(self.protocol._pending_parts, [])

    def test_multi_parcial_packet2(self):
        stream_data = (
            b'CONNECTED\n'
            b'version:1.0\n\n',
            b'\x00\nERROR\n',
            b'header:1.0\n\n',
            b'Hey dude\x00\n',
        )

        for data in stream_data:
            self.protocol.add_data(data)

        frames = self.protocol.pop_frames()
        self.assertEqual(len(frames), 2)

        self.assertEqual(frames[0].command, u'CONNECTED')
        self.assertEqual(frames[0].headers, {u'version': u'1.0'})
        self.assertEqual(frames[0].body, None)

        self.assertEqual(frames[1].command, u'ERROR')
        self.assertEqual(frames[1].headers, {u'header': u'1.0'})
        self.assertEqual(frames[1].body, u'Hey dude')

        self.assertEqual(self.protocol._pending_parts, [])

    def test_multi_parcial_packet_with_utf8(self):
        stream_data = (
            b'CONNECTED\n'
            b'accept-version:1.0\n\n',
            b'\x00\nERROR\n',
            b'header:1.0\n\n\xc3',
            b'\xa7\x00\n',
        )

        for data in stream_data:
            self.protocol.add_data(data)

        self.assertEqual(len(self.protocol._frames_ready), 2)
        self.assertEqual(self.protocol._pending_parts, [])

        self.assertEqual(self.protocol._frames_ready[0].body, None)
        self.assertEqual(self.protocol._frames_ready[1].body, u'ç')

    def test_heart_beat_packet1(self):
        self.protocol._recv_heart_beat = MagicMock()
        self.protocol.add_data(b'\n')

        self.assertEqual(self.protocol._pending_parts, [])
        self.assertTrue(self.protocol._recv_heart_beat.called)

    def test_heart_beat_packet2(self):
        self.protocol._recv_heart_beat = MagicMock()
        self.protocol.add_data(
            b'CONNECT\n'
            b'accept-version:1.0\n\n\x00\n'
        )

        self.assertTrue(self.protocol._recv_heart_beat.called)
        self.assertEqual(self.protocol._pending_parts, [])

    def test_heart_beat_packet3(self):
        self.protocol._recv_heart_beat = MagicMock()
        self.protocol.add_data(
            b'\nCONNECT\n'
            b'accept-version:1.0\n\n\x00'
        )

        frames = self.protocol.pop_frames()
        self.assertEqual(len(frames), 1)

        self.assertEqual(frames[0].command, u'CONNECT')
        self.assertEqual(frames[0].headers, {u'accept-version': u'1.0'})
        self.assertEqual(frames[0].body, None)

        self.assertTrue(self.protocol._recv_heart_beat.called)
        self.assertEqual(self.protocol._pending_parts, [])


class TestBuildFrame(TestCase):

    def setUp(self):
        self.protocol = StompProtocol()

    def test_build_frame_with_body(self):
        buf = self.protocol.build_frame('HELLO', {
            'from': 'me',
            'to': 'you'
        }, 'I Am The Walrus')

        self.assertEqual(
            buf,
            b'HELLO\n'
            b'from:me\n'
            b'to:you\n\n'
            b'I Am The Walrus'
            b'\x00')

    def test_build_frame_without_body(self):
        buf = self.protocol.build_frame('HI', {
            'from': '1',
            'to': '2'
        })

        self.assertEqual(
            buf,
            b'HI\n'
            b'from:1\n'
            b'to:2\n\n'
            b'\x00')


class TestReadFrame(TestCase):

    def setUp(self):
        self.protocol = StompProtocol()

    def test_single_packet(self):
        self.protocol.add_data(
            b'CONNECT\n'
            b'accept-version:1.0\n\n\x00'
        )

        self.assertEqual(len(self.protocol._frames_ready), 1)

        frame = self.protocol._frames_ready[0]
        self.assertEqual(frame.command, 'CONNECT')
        self.assertEqual(frame.headers, {'accept-version': '1.0'})
        self.assertEqual(frame.body, None)
