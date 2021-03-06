#add parent dir to find package. Only needed for source code build, pip install doesn't need it.
import os, inspect
currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(os.path.dirname(currentdir))
os.sys.path.insert(0,parentdir)

import gym, logging
from mpi4py import MPI
from gibson.envs.husky_env import HuskyNavigateEnv
from baselines.common import set_global_seeds
from gibson.utils import pposgd_simple
import baselines.common.tf_util as U
from gibson.utils import cnn_policy, mlp_policy
from gibson.utils import utils
import datetime
from baselines import logger
from gibson.utils.monitor import Monitor
import os.path as osp
import tensorflow as tf
import random
import sys

## Training code adapted from: https://github.com/openai/baselines/blob/master/baselines/ppo1/run_atari.py

def train(num_timesteps, seed):
    rank = MPI.COMM_WORLD.Get_rank()
    #sess = U.single_threaded_session()
    sess = utils.make_gpu_session(args.num_gpu)
    sess.__enter__()
    if args.meta != "":
        saver = tf.train.import_meta_graph(args.meta)
        saver.restore(sess,tf.train.latest_checkpoint('./'))

    if rank == 0:
        logger.configure()
    else:
        logger.configure(format_strs=[])
    workerseed = seed + 10000 * MPI.COMM_WORLD.Get_rank()
    set_global_seeds(workerseed)

    use_filler = not args.disable_filler

    config_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', 'configs', 'husky_navigate_rgb_train.yaml')
    if args.mode=="SENSOR":
        config_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', 'configs', 'husky_navigate_nonviz_train.yaml')
    print(config_file)

    raw_env = HuskyNavigateEnv(gpu_count=args.gpu_count,
                               config=config_file)

    def policy_fn(name, ob_space, ac_space):
        if args.mode == "SENSOR":
            return mlp_policy.MlpPolicy(name=name, ob_space=ob_space, ac_space=ac_space, hid_size=64, num_hid_layers=2)
        else:
            return cnn_policy.CnnPolicy(name=name, ob_space=ob_space, ac_space=ac_space, session=sess, kind='small')
        #else:
            #return fuse_policy.FusePolicy(name=name, ob_space=ob_space, sensor_space=sensor_space, ac_space=ac_space, save_per_acts=10000, session=sess)


    env = Monitor(raw_env, logger.get_dir() and
        osp.join(logger.get_dir(), str(rank)))
    env.seed(workerseed)
    gym.logger.setLevel(logging.WARN)

    
    pposgd_simple.learn(env, policy_fn,
        max_timesteps=int(num_timesteps * 1.1),
        timesteps_per_actorbatch=3000,
        clip_param=0.2, entcoeff=0.0,
        optim_epochs=4, optim_stepsize=3e-3, optim_batchsize=64,
        gamma=0.996, lam=0.95,
        schedule='linear',
        save_name="husky_navigate_ppo_{}".format(args.mode),
        save_per_acts=10,
        sensor=args.mode=="SENSOR",
        reload_name=args.reload_name
    )
    '''
    pposgd_fuse.learn(env, policy_fn,
        max_timesteps=int(num_timesteps * 1.1),
        timesteps_per_actorbatch=1024,
        clip_param=0.2, entcoeff=0.0001,
        optim_epochs=10, optim_stepsize=3e-6, optim_batchsize=64,
        gamma=0.995, lam=0.95,
        schedule='linear',
        save_name=args.save_name,
        save_per_acts=10000,
        reload_name=args.reload_name
    )

    env.close()
    '''

def callback(lcl, glb):
    # stop training if reward exceeds 199
    total = sum(lcl['episode_rewards'][-101:-1]) / 100
    totalt = lcl['t']
    is_solved = totalt > 2000 and total >= -50
    return is_solved


def main():
    train(num_timesteps=10000000, seed=5)

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--mode', type=str, default="RGB")
    parser.add_argument('--num_gpu', type=int, default=1)
    parser.add_argument('--gpu_count', type=int, default=0)
    parser.add_argument('--disable_filler', action='store_true', default=False)
    parser.add_argument('--meta', type=str, default="")
    parser.add_argument('--resolution', type=str, default="SMALL")
    parser.add_argument('--reload_name', type=str, default=None)
    parser.add_argument('--save_name', type=str, default=None)
    args = parser.parse_args()
    main()
