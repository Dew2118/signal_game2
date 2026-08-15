import importlib.util
import pathlib
import unittest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("signal_game", PROJECT_ROOT / "__main__.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
Game = MODULE.Game


class DummyDisplay:
    def __init__(self):
        self.colors = {}

    def add_log(self, *args, **kwargs):
        pass

    def set_char_color_at_coord(self, x, y, color_name, game, is_flashing_call=False):
        self.colors[(x, y)] = color_name

    def get_char_color_at_coord(self, x, y, lines):
        return self.colors.get((x, y))


class ApproachTests(unittest.TestCase):
    def test_setup_approach_detects_left_side_approach(self):
        game = Game("aaaa\\xaaaa", DummyDisplay(), "test")
        game.setup_approach()

        self.assertIn((5, 0), game.approach_map)
        self.assertEqual(game.approach_map[(5, 0)]["coords"], [(1, 0), (2, 0), (3, 0), (4, 0)])

    def test_check_approach_uses_backlog_headcode(self):
        game = Game("aaaa\\xaaaa", DummyDisplay(), "test")
        game.setup_approach()
        game.backlog_train_spawn = [{"start_coord": (5, 0), "headcode": "2B12"}]

        game.check_approach()

        self.assertEqual(game.lines[0][1], "2")
        self.assertEqual(game.lines[0][2], "B")
        self.assertEqual(game.lines[0][3], "1")
        self.assertEqual(game.lines[0][4], "2")


if __name__ == "__main__":
    unittest.main()
