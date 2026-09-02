from importlib import import_module
import unittest
from unittest.mock import MagicMock, patch

from engine import Engine  # noqa: F401 - establishes the project's import order
from game.element.damage_property import DamageProperty
from game.message import Message


class TestOverkillDamageModifiers(unittest.TestCase):

    def test_exploit_weakness_increases_damage_to_overkill_target(self):
        exploit_weakness = import_module(
            "cards.pack.cyclops.cyclops.33005"
        ).GetAbilities()[1]
        effect = MagicMock()
        message = object.__new__(Message.WhenUnitWouldTakeDamage)
        message.property = DamageProperty(
            damage=8,
            is_from_overkill=True,
        )
        message.would_atk_message = MagicMock()

        with patch("game.message.Message.WhenDamageUpdated_Text") as updated:
            exploit_weakness.operation(effect, message)

        self.assertEqual(message.property.damage, 9)
        updated.assert_called_once_with(1, effect)

    def test_damage_increase_excludes_overkill_unless_requested(self):
        effect = MagicMock()
        message = object.__new__(Message.WhenUnitWouldTakeDamage)
        message.property = DamageProperty(
            damage=8,
            is_from_overkill=True,
        )
        message.would_atk_message = MagicMock()

        with patch("game.message.Message.WhenDamageUpdated_Text") as updated:
            message.IncreaseDamage(1, effect)

        self.assertEqual(message.property.damage, 8)
        updated.assert_not_called()


if __name__ == "__main__":
    unittest.main()
