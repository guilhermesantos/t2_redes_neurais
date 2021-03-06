import numpy as np
import imageio
import math
import pickle
import os
import json
from sklearn.cluster import KMeans

#Classe que representa a rede RBF
class RBFNet():
	#Construtor. Recebe o tamanho da cadama de entrada, centroides, dispersao, tamanho da camada de saida
	#e taxa de aprendizado
	def __init__(self, input_length, centers, spread, output_length, learning_rate=5e-1):
		self.input_length = input_length
		self.centers = np.array(centers)
		self.spread = spread
		self.hidden_length = self.centers.shape[0]
		print('HIDDEN LAYER LENGTH', self.hidden_length)
		self.output_length = output_length
		self.learning_rate = learning_rate
		self.output_activ = self.sigmoid
		self.output_activ_deriv = self.sigmoid_deriv

		#Inicializa os pesos da camada de saida aleatoriamente, representado-os na forma de matriz
		#Os pesos e vies de cada neuronio sao dispostos em linhas
		#Em hidden_length+1, o +1 serve para representar o vies
		self.output_layer = np.random.uniform(-0.5, 0.5, (self.output_length, self.hidden_length+1))

	def save_to_disk(self, file_name):
		print('Saving model to', file_name)
		with open(file_name, 'wb') as file:
			pickle.dump(self, file)

	#Funcao de ativacao da camada oculta (gaussiana)
	#net, neste caso, é só o dado de entrada (nao tem camada anterior à camada RBF)
	def gaussian(self, net):
		#Cria um vetor com a distancia da entrada para cada centroide
		dists = np.array([np.linalg.norm(net - self.centers[i]) for i in range(self.centers.shape[0])])
		#Calcula a funcao de ativacao (gaussiana) para cada distancia
		fnet = np.exp(-((dists**2)/(2*(self.spread**2))))
		return fnet

	def sigmoid(self, net):
		return (1./(1.+math.exp(-net)))

	def sigmoid_deriv(self, fnet):
		one_vector = np.ones(fnet.shape)
		return fnet*(one_vector-fnet)

	def linear(self, net):
		return net

	def linear_deriv(self, fnet):
		return fnet

	#Faz forward propagation, retornando apenas o vetor produzido pela camada de saida
	#Isto eh feito porque, para usos do forward propagation fora do treinamento, 
	#nao interessa saber o valor produzido pela camada oculta
	def forward(self, input_vect):
		return self.forward_training(input_vect)[2]

	#Faz forward propagation (calcula a predicao da rede)
	#Retorna tanto a saida da camada oculta quanto da camada de saida, 
	#usados no algoritmo de treinamento
	def forward_training(self, input_vect):
		input_vect = np.array(input_vect)
		#Checa se o tamanho da entrada corresponde ao que eh esperado pela rede
		if(input_vect.shape[0] != self.input_length):
			message = 'Tamanho incorreto de entrada. Recebido: {} || Esperado: {}'.format(input_vect.shape[0], self.input_length)
			raise Exception(message)

		#Passa o vetor de entrada pela camada oculta, calculando a sua distancia para cada centroide
		hidden_fnet = self.gaussian(input_vect)

		#Adiciona um componente "1" ao vetor produzido pela camada oculta para permitir calculo do bias
		#na camada de saida
		biased_hidden_activ = np.zeros((self.hidden_length+1))
		biased_hidden_activ[0:self.hidden_length] = hidden_fnet[:]
		biased_hidden_activ[self.hidden_length] = 1
		
		#Calcula a transformacao feita pela camada de saida usando produto de matriz por vetor
		#Wo x H = net, sendo Wo a matriz de pesos da camada de saida e H o vetor produzido pela ativacao
		#da camada oculta
		out_net = np.dot(self.output_layer, biased_hidden_activ)
		out_fnet = np.array([self.output_activ(x) for x in out_net])
		

		#Retorna ativacao da camada oculta 
		return hidden_fnet, out_net, out_fnet

	#Treina a rede aplicando recursive least-squares (RLS)
	def fit(self, input_samples, target_labels, absolute_threshold, relative_threshold, learning_rate=None):
		if(learning_rate is not None):
			self.learning_rate = learning_rate

		#Erro quadratico medio eh inicializado com um valor arbitrario (maior que o threshold de parada)
		#p/ comecar o treinamento
		mean_squared_error = 2*absolute_threshold
		previous_mean_squared_error = 0.001
		relative_error = 1.0

		#Inicializa o numero de epocas ja computadas
		epochs = 0

		#Enquanto não chega no erro quadratico medio desejado ou atingir 5000 epocas, continua treinando
		while(mean_squared_error > absolute_threshold and epochs < 50000 and relative_error > relative_threshold):
			#Erro quadratico medio da epoca eh inicializado com 0
			previous_mean_squared_error = mean_squared_error
			mean_squared_error = 0
			
			#Passa por todos os exemplos do dataset
			for i in range(0, input_samples.shape[0]):
				#if(i % 200 == 0):
				#	print('Adjusting for sample', i)
				#Pega o exemplo da iteracao atual
				input_sample = input_samples[i]
				#Pega o label esperado para o exemplo da iteracao atual
				target_label = target_labels[i]

				#Pega net e f(net) da camada oculta e da camada de saida
				hidden_fnet, out_net, out_fnet = self.forward_training(input_samples[i])
				
				#Cria um vetor com o erro de cada neuronio da camada de saida
				error_array = -(target_label - out_fnet)
				#print('target label', target_label)
				#print('out fnet', out_fnet)
				#print('error array', error_array)


				#Calcula a variacao dos pesos da camada de saida com a regra delta generalizada
				#delta_o_pk = (Ypk-Ok)*Opk(1-Opk), sendo p a amostra atual do conjunto de treinamento,
				#e k um neuronio da camada de saida. Ypk eh a saida esperada do neuronio pelo exemplo do dataset,
				#Opk eh a saida de fato produzida pelo neuronio
				#delta_output_layer = error_array * self.output_activ_deriv(np.array(out_fnet))
				hidden_fnet_with_bias = np.zeros(hidden_fnet.shape[0]+1)
				hidden_fnet_with_bias[0:self.hidden_length] = hidden_fnet[:]
				hidden_fnet_with_bias[self.hidden_length] = 1
				
				#Atualiza os pesos da camada de saida
				#Wkj(t+1) = wkj(t) + eta*deltak*Ij
				#for neuron in range(0, self.output_length):
				#	for weight in range(0, self.output_layer.shape[1]):
				#		self.output_layer[neuron, weight] = self.output_layer[neuron, weight] - \
				#			self.learning_rate * out_fnet[neuron] * hidden_fnet_with_bias[weight]
				for neuron in range(0, self.output_length):
					for weight in range(0, self.output_layer.shape[1]):
						self.output_layer[neuron, weight] = self.output_layer[neuron,weight]\
							- hidden_fnet_with_bias[weight]*error_array[neuron]*learning_rate


				#O erro da saída de cada neuronio é elevado ao quadrado e somado ao erro total da epoca
				#para calculo do erro quadratico medio ao final
				mean_squared_error = mean_squared_error + np.sum(error_array**2)	
					
			
			#Divide o erro quadratico total pelo numero de exemplos para obter o erro quadratico medio
			mean_squared_error = mean_squared_error/input_samples.shape[0]
			relative_error = math.fabs(mean_squared_error-previous_mean_squared_error)/previous_mean_squared_error

			epochs = epochs + 1
			if(epochs % 100 == 0):
				print('End of epoch no. {}. rmse={}'.format(epochs, mean_squared_error))

		print('Total epochs run', epochs)
		print('Final rmse', mean_squared_error)
		return None

def normalize(data, range_min, range_max):
	data_min = np.min(data)
	data_max = np.max(data)

	if(data.shape[0] == 1):
		normalized = (data/data_max)*(range_max-range_min)+range_min
	else:
		normalized = ((data-data_min)/(data_max-data_min))*(range_max-range_min)+range_min
	return normalized

#Testa a mlp com funcoes logicas
def test_logic():
	zero_center = np.array([0,0])
	one_center = np.array([1,1])

	x = np.array([[0,0],[0,1],[1,0],[1,1]])
	centers = np.array([[0,0],[1,1]])
	target = np.array([0, 1, 1, 0])
	rbf = RBFNet(input_length=2, centers=centers, spread=1.0, output_length=1)

	print('\n\noutput before backpropagation')
	print('[0,0]=', rbf.forward([0,0]))
	print('[0,1]=', rbf.forward([0,1]))
	print('[1,0]=', rbf.forward([1,0]))
	print('[1,1]=', rbf.forward([1,1]))
	
	rbf.fit(input_samples=x, target_labels=target, absolute_threshold=10e-5, relative_threshold=10e-8, learning_rate=10e-1)

	print('\n\noutput after backpropagation')
	print('[0,0]=', rbf.forward([0,0]))
	print('[0,1]=', rbf.forward([0,1]))
	print('[1,0]=', rbf.forward([1,0]))
	print('[1,1]=', rbf.forward([1,1]))

#Carrega o dataset de digitos
def load_digits():
	data = np.zeros([1593, 256])
	labels = np.zeros([1593, 10])

	with open('semeion.data') as file:
		for image_index, line in enumerate(file):
			number_list = np.array(line.split())
			image = number_list[0:256].astype(float).astype(int)
			classes = number_list[256:266].astype(float).astype(int)
			data[image_index,:] = image[:]
			labels[image_index,:] = classes[:]
			
	return data, labels

#Plota uma imagem
def plot_image(image):
	news_image = image.reshape(16,16)
	plt.imshow(new_image)
	plt.show()

#Faz predicao da classe de todos os dados e compara com as classes esperadas
def measure_score(network, data, target):
	dataset_size = target.shape[0]
	score = 0
	
	for index, data in enumerate(data):
		expected_class = np.argmax(target[index])
		print('expected', expected_class)
		network_output = network.forward(data)
		print('output', network_output)
		predicted_class = np.argmax(network_output)
		print('predicted', predicted_class)
		if(expected_class == predicted_class):
			score += 1

	return score, (score/dataset_size)*100	

#Embaralha dois arrays de forma simetrica
def shuffle_two_arrays(data, labels):
	permutation = np.random.permutation(data.shape[0])
	return data[permutation], labels[permutation]

#Gera os indices de cada um dos k-folds
#ex: dataset de 10 elementos dividido em 5 folds
#retorna [[0,1][2,3][4,5][6,7][8,9]], em que o n-esimo vetor interno
#tem os indices dos elementos que pertencem ao n-esimo fold 
def k_folds_split(dataset_size, k):
	fold_size = int(dataset_size/k)
	folds = np.zeros((k, fold_size), dtype=int)

	for current_k in range(0, k):
		fold_indexes = range(current_k*fold_size, (current_k+1)*fold_size)
		folds[current_k] = fold_indexes

	print('folds', folds)
	return folds

#Recebe os folds e retorna as listas (dos indices) dos elementos que pertencem 
#ao conjunto de treinamento e de teste, para todos os testes
#ex. se tem 10 folds, retorna 10 listas de treino e 10 de teste
#o primeiro par (treino, teste) usa o primeiro fold para teste e os demais para treino, o segundo
#par (treino, teste) usa o segundo fold para teste e os demais para treino, e assim por diante
#Retorna estes conjuntos no formato de uma lista de indices dos elementos que pertencem a cada
#conjunto
def train_test_split(folds):
	fold_qtt = folds.shape[0]
	fold_size = folds.shape[1]
	train_set_size = (fold_qtt-1)*fold_size
	test_set_size = fold_size

	train_sets = np.zeros((fold_qtt, train_set_size), dtype=int)
	test_sets = np.zeros((fold_qtt, test_set_size), dtype=int)

	for fold_to_skip in range(0, fold_qtt):
		train_set = np.zeros(train_set_size, dtype=int)
		test_set = np.zeros(test_set_size, dtype=int)
		added_folds = 0

		for fold_index, current_fold in enumerate(folds):
			if(fold_index != fold_to_skip):
				train_set[added_folds*fold_size:(added_folds+1)*fold_size] = current_fold
				added_folds += 1
			else:
				test_set[0:fold_size] = current_fold

		train_sets[fold_to_skip] = train_set
		test_sets[fold_to_skip] = test_set

	return train_sets, test_sets

#Faz k-fold cross validation em uma rbf
def k_fold_cross_validation(data, labels, k):
	print('k-fold cross validation')
	print('Shuffling data...')
	shuffled_data, shuffled_labels = shuffle_two_arrays(data, labels)
	print('Splitting in folds')
	folds = k_folds_split(shuffled_data.shape[0], 5)
	print('Building train and test set indexes...')
	train_sets, test_sets = train_test_split(folds)
	
	scores = []
	accuracies = []
	for index, (train_set, test_set) in enumerate(zip(train_sets, test_sets)):
		#print('Performing validation with fold no. {}...'.format(index))
		#print('Training...')
		input_length = data[train_set].shape[1]
		output_length = labels[test_set].shape[1]
		
		centers = KMeans(n_clusters=k, n_init=20, max_iter=500).fit(data[train_set]).cluster_centers_
		rbf = RBFNet(input_length=input_length, centers=centers, spread=1.0, output_length=output_length)
		
		rbf.fit(input_samples=data[train_set], target_labels=labels[train_set], 
			absolute_threshold=5e-5, relative_threshold=10e-6, learning_rate=5e-1)

		score, accuracy = measure_score(rbf, data[test_set], labels[test_set])
		scores.append(score)
		accuracies.append(accuracy)

	print('===========================')
	print('NUMBER OF CENTERS', rbf.hidden_length)
	print('AVERAGE ACCURACY', np.sum(accuracies)/len(accuracies))
	print('===========================')
	result_dict = build_test_result_dict(rbf, scores, accuracies)

	return scores, accuracies, result_dict

#Grava os resultados do teste em um arquivo .json
def record_test_results(test_results, filename):
	print('Recording test results to', filename)
	with open(filename, 'w') as file:
		json.dump(test_results, file)

#Compoe os resultados do teste em um dicionario pra facilitar gravacao
def build_test_result_dict(rbf, scores, accuracies):
	test_results = dict()
	test_results['hidden_layer_size'] = rbf.hidden_length
	test_results['learning_rate'] = rbf.learning_rate
	test_results['scores'] = scores
	test_results['accuracies'] = accuracies
	return test_results

def main():
	#test_logic()
	data, labels = load_digits()
	#Testa a rede variando o número de funções RBF e mantendo fixa a taxa de aprendizado
	tests = []
	for center_quantity in range(1, 20):
		print('Testing for center quantity', center_quantity)
		scores, accuracies, test_result_dict = k_fold_cross_validation(data, labels, center_quantity)
		tests.append(test_result_dict)
	record_test_results(tests, 'hidden_layer_results.json')
	
	'''
	#Testa a rede mantendo fixo o tamanho da camada oculta e variando a taxa de aprendizado
	tests = []
	for learning_rate in np.arange(10e-2, 1, 10e-2):
		print('Testing for learning rate', learning_rate)
		rbf = RBFNet(*[256, 128, 10], learning_rate)
		scores, accuracies = k_fold_cross_validation(rbf, data, labels, 5)
		tests.append(build_test_result_dict(rbf, scores, accuracies))
	record_test_results(tests, 'learning_rate_results.json')'''

if __name__ == '__main__':
	main()