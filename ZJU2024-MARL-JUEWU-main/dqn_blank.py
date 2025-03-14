import copy
import random
import numpy as np

import gymnasium as gym
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from replaybuffer import ReplayBuffer


class QNetwork(nn.Module):
    def __init__(self, env):
        super().__init__()
        '''
        定义一个三层神经网络，其中
        输入层：全连接层： 状态空间作为输入，256作为输出，Relu激活函数
        中间层：全连接层：256输入256输出，Relu激活
        输出层：全连接层：256输入，动作空间输出
        '''
        self.network = nn.Sequential(
            nn.Linear(env.observation_space.shape[0], 256),nn.ReLU(),
            nn.Linear(256, 256),nn.ReLU(),
            nn.Linear(256, env.action_space.n),
        )
    def forward(self, x):
        '''
        前向计算
        '''
        return self.network(x)


if __name__ == "__main__":
    # Parameters
    learning_rate = 3e-4
    buffer_size = int(1e6)
    total_timesteps = int(1e6)
    epsilon = 0.01
    gamma = 0.99
    tau = 1.0

    learning_starts = 80000
    train_frequency = 4
    log_frequency = 50
    target_frequency = 1000
    batch_size = 256

    # wandb.init(project="DQN", name="Freeway")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    env = gym.make("ALE/Freeway-v5", obs_type="ram")
    eval_env = gym.make("ALE/Freeway-v5", obs_type="ram")
   
    '''
    定义两个网络，分别为q_network,以及target_network；
    定义优化器，训练网络
    '''
    q_network = QNetwork(env).to(device)    
    target_network = copy.deepcopy(q_network)    
    optimizer = optim.Adam(q_network.parameters(), lr=learning_rate)  


    buffer = ReplayBuffer(env.observation_space.shape[0], env.action_space.n, buffer_size, device)

    obs, _ = env.reset()
    total_rewards = []
    total_reward = 0
    for step in range(total_timesteps):

        '''
        实现epsilon-greedy算法，epsilon为给定超参
        '''
        if random.random() < epsilon:  
            actions = env.action_space.sample() 
        else:  
        # Exploiting known actions  
        # Assuming q_values is the output from your Q-network for the current state  
            q_values = q_network(torch.tensor(obs, device=device,dtype=torch.float32))
            actions = q_values.argmax().item()  
        
        if type(actions) == np.ndarray:
            actions = actions.item()


        next_obs, rewards, terminations, truncations, infos = env.step(actions)
        total_reward += rewards

        real_next_obs = infos["final_observation"] if truncations else next_obs.copy()
        buffer.add(obs, actions, real_next_obs, rewards, terminations)
        obs = next_obs

        if terminations:
            obs, _ = env.reset()
            total_rewards.append(total_reward)
            total_reward = 0

        # Training.
        if step > learning_starts:
            if step % train_frequency == 0:
                data = buffer.sample(batch_size)
                buffer_obs, act, next_buffer_obs, rew, cont = data

                '''
                计算td_target
                Q(s,a) (old_val)
                '''
                with torch.no_grad():
                    target_max = target_network(buffer_obs).max(dim=1,keepdim =True)[0]
                    td_target = rew + (gamma * target_max * cont)  
        
                # Compute Q-values for the current state-action pairs  
                old_val = q_network(buffer_obs).gather(1, act)  


                loss = F.mse_loss(td_target, old_val)

                if step % log_frequency == 0:
                    # wandb.log({"td_loss": loss.item(), "q_values": old_val.mean().item()}, step=step)
                    print('td_loss: {}\t q_values: {}\t step: {}, avg_rewards: {}'.format(loss.item(), old_val.mean().item(), step, np.mean(total_rewards[-100:])))
                    pass
                
                # optimize the model
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()

            # update target network
            if step % target_frequency == 0:
                for target_param, param in zip(target_network.parameters(), q_network.parameters()):
                    target_param.data.copy_(tau * param.data + (1.0 - tau) * target_param.data)

    env.close()
    model_path = f"Freeway-runs/DQN.pt"
    torch.save(q_network.state_dict(), model_path)