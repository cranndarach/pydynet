"""
network.py

This module controls the construction of a network of oscillators.

@author: Kevin S. Brown (University of Connecticut), Ann M. Hermundstad (UPenn)

"""

from __future__ import division
from utilities import randchoice
from numpy import zeros,ones,arange,empty_like,where,reshape,asarray
from numpy import sqrt,cos,sin,pi,mod,round,all
from numpy import mean,var
from numpy import uint8,float64,int
import networkx as nx
import eulerint


def dydtMS(y,t,p):
    """
    Mirollo-Strogatz linear governing equation for oscillator dynamics.

            dydt = -p[0]*y + p[1]

    Parameter values from Mirollo and Strogatz 1989:
            p[0] = 1
            p[1] = 2
    """
    return -p[0]*y + p[1]



class PulseOscillatorNetwork(nx.Graph):

    def __init__(self,N,topology,*args):
        super(PulseOscillatorNetwork,self).__init__()
        # dispatch on topology type
        tdict = {'empty':self.connect_empty, 'full':self.connect_full, 'ring':self.connect_ring, 'fixed degree':self.connect_fixed_degree,
                 'fixed edges':self.connect_fixed_edges,'ER':self.connect_erdos_renyi, 'WS':self.connect_watts_strogatz,
                 'BA':self.connect_barabasi_albert}
        if tdict.has_key(topology):
            tdict[topology](N,*args)
        else:
            print 'ERROR.  Unrecognized graph topology. Defaulting to ring.'
            self.connect_ring(N)
        # set default amplitude/delay/threshold parameters for dynamical simulations
        self.eps = 0.3
        self.delta = 0
        self.y_th = 1.0


    def is_connected(self):
        """
        Returns True if the graph is connected (no disconnected subgraphs), False otherwise.
        """
        return nx.algorithms.is_connected(self)


    def number_of_edges(self):
        """
        Returns the number of edges in the graph.
        """
        return len(self.edges())


    def degree_mean_var(self):
        """
        Returns the mean and variance of the node degrees.
        """
        return mean(self.degree().values()),var(self.degree().values())


    def length_mean_var(self):
        """
        Returns the mean and variance of the edge lengths.
        """
        lsum = 0.0
        l2sum = 0.0
        for e1,e2 in self.edges():
            l = self[e1][e2]['length']
            lsum += l
            l2sum += l*l
        lmean = lsum/self.number_of_edges()
        return lmean,(l2sum/self.number_of_edges() - lmean*lmean)


    def connect_empty(self,N):
        """
        Adds N nodes to the graph, but no edges.  This can be used to clear the graph without deleting
        the object.
        """
        self.remove_nodes_from(self.nodes())
        # re-add desired number of nodes
        self.add_nodes_from(range(0,N))


    def connect_full(self,N,p):
        """
        Each node is connected to every other node; all N nodes have degree N-1.
        """
        self.connect_empty(N)
        self.add_edges_from(nx.random_regular_graph(N-1,N).edges())


    def connect_ring(self,N):
        """
        Each of the N nodes is connected to its 'neighbors' (node N to N-1 and N+1, modulo N).
        The neighbors are only meaningful once a distance embedding is chosen; if the unit circle
        mapping is chosen, this topolgy gives a ring with nearest neighbor connections.
        """
        self.connect_empty(N)
        for n in self.nodes():
            self.add_edge(n,mod(n+1,N))
            self.add_edge(n,mod(n+N-1,N))


    def connect_fixed_degree(self,N,p):
        """
        All nodes have identical degree; they are each randomly connected to p*N other nodes.
        If p > 1 - 1/N, this will return the regular, fully connected graph.'
        """
        self.connect_empty(N)
        d = int(p*N)
        self.add_edges_from(nx.random_regular_graph(d,N).edges())


    def connect_fixed_edges(self,N,p):
        """
        A fixed fraction of the total possible N*(N-1)/2 connections are made. (Not a binomial
        graph!  The number of edges is always p*N(N-1)/2, not just in the N->infinity limit.)
        """
        self.connect_empty(N)
        dN = int(p*N*(N-1)/2)
        self.add_edges_from(nx.gnm_random_graph(N,dN).edges())


    def connect_erdos_renyi(self,N,p):
        """
        Erdos-Renyi (Poisson random) graph G(N,p).
        """
        # this is kind of a dumb way to do this
        self.connect_empty(N)
        self.add_edges_from(nx.gnp_random_graph(N,p).edges())


    def connect_barabasi_albert(self,N,m):
        """
        Barabasi-Albert preferential attachment graph with N nodes and m
        edges from each new node to existing nodes.
        """
        if m > N:
            m = N-1
        # again, not the best way to do this
        self.connect_empty(N)
        self.add_edges_from(nx.barabasi_albert_graph(N,m).edges())


    def connect_watts_strogatz(self,N,p):
        """
        Newman-Watts-Strogatz graph staring with a ring.  Each node is wired to
        its nearest neighbors on the ring and then additional edges are added
        with probability p.
        """
        # ditto
        self.connect_empty(N)
        self.add_edges_from(nx.newman_watts_strogatz_graph(N,2,p).edges())


    def set_edge_lengths(self,embedding):
        """
        Sets the 'length' attribute of the graph edges according to some physical mapping, stored
        in a DistanceEmbedding object.
        """
        for e1,e2 in self.edges():
            self[e1][e2]['length'] = embedding.distances[e1,e2]
        return


    def euler_integrate(self,p,y0,T,M=10000,fullout=True,stopatsync=False):
        """
        Integrates (using the Euler method) a delayed pulse-oscillator network.
        Currently, only one kind of RHS (Mirollo-Strogatz) is supported.

        INPUT:
            p : array, required
                parameters required for RHS dydt (cannot be none!)

            y0 : array, required
                vector of initial conditions, length equal to number of nodes in network

            T : float, required
                total integration time (integration is performed from 0 to T)

            M : integer, optional
                total number of steps in the integration

            fullout : boolean, optional
                    if fullout == True, an array of size nNodes x M will be returned, giving
                    y(t) at all M simulation steps.  Set to False to return only y(T).

            stopatsync : boolean, optional
                    if stopatsync == True, the integration will terminate as soon as all
                    the nodes are synchronized (i.e., all reset in the same step before
                    pulses are resolved)

        OUTPUT:
            y : amplitudes for each node at all simulation times (output == 'full') or just
                the final integration time (output == 'final')

        OUTPUT:

            from [0,T]
        using M total steps.  Returns the final values for the node amplitudes.
        """
        # lots of massaging to:
        #   1. maintain type consistency with the cython/C call
        #   2. avoid passing too many python objects/functions into the C call
        # booleans to uint8
        fo = uint8(0)
        if fullout is True:
            fo = uint8(1)
        sos = uint8(0)
        if stopatsync is True:
            sos = uint8(1)
        # make sure parameters are floats
        p = p.astype(float64)
        # type and shape of y0
        y0 = asarray(y0).reshape((len(self.nodes()),1)).astype(float64)
        # things to try to avoid lots of python object access
        yth = float64(self.y_th)
        delta = float64(self.delta)
        eps = float64(self.eps)
        lengthAdj = zeros((len(self.nodes()),len(self.nodes())),dtype=float64)
        for i in xrange(len(self.nodes())):
            nlist = self.neighbors(i)
            for n in nlist:
                lengthAdj[i,n] = self[i][n]['length']
        # make the call to the integrator
        y = eulerint.euler_integrate(lengthAdj,p,y0,yth,delta,eps,T,M,fo,sos)
        return y
'''
        # sets up storage for y, pulses, and sets the ICs
        y = zeros((len(self.nodes()),M+1))
        pulses = zeros((len(self.nodes()),M+1))
        y[:,0] = y0.flatten()
        # size of timestep
        dt = T/M
        # start stepping (M+1 ensures we store 0,dt,2*dt,...,M*dt=T)
        for i in xrange(1,M+1):
            # --- Check threshold ---
            nodesToReset = where(y[:,i-1] > self.y_th)[0]
            for n in nodesToReset:
                y[n,i-1] = 0
                for nn in self.neighbors(n):
                    # here's where we use the distances
                    delay_ij = self.delta*round(self[n][nn]['length']/dt)
                    # if a pulse is to be added after T, ignore it (it will never fire)
                    if i-1+delay_ij < M+1:
                        pulses[nn,i-1+delay_ij] += self.eps

            # --- Check for synchronization ---
            if all(y[:,i-1] < 1.0e-10) and stopatsync:
                if fullout is False:
                    return reshape(y[:,-1],y0.shape)
                else:
                    return y

            # --- Resolve pulses---
            y[:,i-1] += pulses[:,i-1]

            # --- Euler step
            y[:,i] = y[:,i-1] + dt*dydt(y[:,i-1],(i-1)*dt,p)

        # integration finished
        if fullout is False:
            # just return y(T), in same shape as y0
            return reshape(y[:,-1],y0.shape)
        # return solution at all nodes, all timesteps
        return y
'''




class DistanceEmbedding(object):
    """
    Calculates node-node distances for a different physical embeddings of a graph.
    Each call to a map function will replace the current distance matrix (distances)
    with a new one, recalculated as described.  If the number of nodes in the graph
    changes, you must re-initialize the embedding as well.

    Methods:

        null_map():
            All distances are equal and of unit magnitude.

        unitcirc_map():
            Equal spacing of the N nodes on a unit circle.

    """
    def __init__(self,N):
        self.N = N
        self.distances = zeros((self.N,self.N))


    def null_map(self):
        """
        All distances are assumed to be equal and unit magnitude (no embedding).
        """
        self.distances = ones((self.N,self.N))
        # zero out self distances
        for i in xrange(self.N):
            self.distances[i,i] = 0.0
        return


    def unitcirc_map(self):
        """
        Assign each node to a position on the unit circle, equally spaced.
        Node 0 is closest to nodes N-1 and 1, 1 closest to 0 and 2, etc.
        """
        dtheta = 2*pi/self.N
        x = cos(arange(self.N)*dtheta)
        y = sin(arange(self.N)*dtheta)
        for i in xrange(self.N):
            for j in xrange(i+1,self.N):
                self.distances[i,j] = sqrt((x[i]-x[j])**2 + (y[i]-y[j])**2)
                self.distances[j,i] = self.distances[i,j]
        return
