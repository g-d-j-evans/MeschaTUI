import pytest
from meshchat_ui.tui.app import MeshChatApp

def test_split_message_no_split():
    app = MeshChatApp()
    message = "Hello world"
    segments = app._split_message(message, limit=129)
    assert segments == ["Hello world"]

def test_split_message_exact_limit():
    app = MeshChatApp()
    message = "a" * 129
    segments = app._split_message(message, limit=129)
    assert segments == ["a" * 129]

def test_split_message_split_at_space():
    app = MeshChatApp()
    # Message is 10 chars, split at 5. "Hello world" (11 chars)
    message = "Hello world"
    segments = app._split_message(message, limit=5)
    assert segments == ["Hello", "world"]

def test_split_message_split_at_limit_no_space():
    app = MeshChatApp()
    message = "abcdefghij"
    segments = app._split_message(message, limit=5)
    assert segments == ["abcde", "fghij"]

def test_get_message_length_channel():
    app = MeshChatApp()
    # "<channel> <message>"
    input_val = "#general hello world"
    assert app._get_message_length(input_val) == 11

def test_get_message_length_command():
    app = MeshChatApp()
    # "/command <args>"
    input_val = "/join #test"
    assert app._get_message_length(input_val) == 0

def test_get_message_length_empty():
    app = MeshChatApp()
    assert app._get_message_length("") == 0
