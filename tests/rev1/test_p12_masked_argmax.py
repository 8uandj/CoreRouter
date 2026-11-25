import unittest
from types import SimpleNamespace

import numpy as np
import torch
from sb3_contrib.common.maskable.distributions import MaskableCategorical

from src.analytics.benchmark.benchmark_algorithm import model_loader


class TestP12MaskedArgmax(unittest.TestCase):
    def helper(self):
        self.assertTrue(hasattr(model_loader, "deterministic_masked_argmax"))
        return model_loader.deterministic_masked_argmax

    def test_matches_maskable_categorical_for_regular_action_space(self):
        logits = torch.tensor([[0.2, 1.7, -0.4, 0.8]], dtype=torch.float32)
        masks = np.array([[True, False, True, True]])
        expected = MaskableCategorical(logits=logits, masks=masks).probs.argmax(dim=-1).cpu().numpy()
        actual = self.helper()(logits, masks)
        np.testing.assert_array_equal(actual, expected)

    def test_handles_float32_simplex_roundoff_at_ten_thousand_actions(self):
        logits = torch.cat((torch.tensor([0.0]), torch.linspace(-15.2, -14.7, 9999))).unsqueeze(0)
        masks = np.ones((1, 10000), dtype=bool)
        self.assertGreater(abs(float(torch.softmax(logits, -1).sum(-1).item()) - 1.0), 1e-6)
        actual = self.helper()(logits, masks)
        np.testing.assert_array_equal(actual, np.array([0]))

    def test_rejects_empty_action_mask(self):
        logits = torch.tensor([[0.0, 1.0]])
        with self.assertRaisesRegex(ValueError, "at least one action"):
            self.helper()(logits, np.array([[False, False]]))

    def test_policy_action_uses_masked_actor_logits(self):
        layer = torch.nn.Linear(2, 4)
        with torch.no_grad():
            layer.weight.zero_()
            layer.bias.copy_(torch.tensor([0.0, 2.0, 5.0, 1.0]))

        class FakePolicy:
            action_net = layer
            mlp_extractor = staticmethod(lambda features: (features, None))

            def set_training_mode(self, training):
                self.training = training

            def obs_to_tensor(self, observation):
                return torch.as_tensor(observation, dtype=torch.float32), True

            def extract_features(self, observation):
                return observation

        model = SimpleNamespace(policy=FakePolicy())
        action = model_loader.deterministic_masked_policy_action(
            model, np.array([[1.0, 2.0]], dtype=np.float32),
            np.array([[True, True, False, True]]),
        )
        np.testing.assert_array_equal(action, np.array([1]))


if __name__ == "__main__":
    unittest.main()
