from unittest.mock import Mock
import numpy as np


def test_main_training_uses_explicit_budget_seed_data_and_output_without_training(monkeypatch, tmp_path):
    from src.analytics.training import train_v11 as trainer
    env = Mock()
    model = Mock(num_timesteps=64)
    monkeypatch.setattr(trainer, 'SubprocVecEnv', Mock(side_effect=AssertionError('smoke must use one env')))
    monkeypatch.setattr(trainer, 'DummyVecEnv', Mock(return_value=env))
    monkeypatch.setattr(trainer, 'VecMonitor', lambda value: value)
    monkeypatch.setattr(trainer, 'VecNormalize', Mock(side_effect=lambda value, **kwargs: value))
    factory = Mock(return_value=model)
    monkeypatch.setattr(trainer, 'MaskablePPO', factory)
    for callback in ['MaskableEvalCallback', 'CheckpointCallback', 'CallbackList']:
        monkeypatch.setattr(trainer, callback, Mock())
    dataset = tmp_path / 'data.csv'
    dataset.write_text('x\n1\n')
    trainer.train_dgrl('vietnam', total_steps=64, n_envs=1, rollout_steps=32,
                       seed=17, data_path=str(dataset), model_dir=str(tmp_path / 'models'))
    assert factory.call_args.kwargs['seed'] == 17
    assert factory.call_args.kwargs['n_steps'] == 32
    assert model.learn.call_args.kwargs['total_timesteps'] == 64
    assert str(tmp_path / 'models') in model.save.call_args.args[0]
    env.save.assert_called_once()
    assert env.close.call_count >= 1
