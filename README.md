hiveary-logs
============

About
-----

Hiveary Log clustering algorithm by Hiveary, Inc.
Version 1.0.0

The Hiveary log clustering algorithm is built upon previous research in extracting event probability from semi-structured log data.

Inspiration drawn from:

Clustering Event Logs Using Iterative Partitioning
Makanju, Nur Zincir-Heywood,  Milios of Dalhousie University
https://web.cs.dal.ca/~zincir/bildiri/kdd09-ane.pdf

A Lightweight Algorithm for Message Type Extraction in Event Logs ∗
Makanju, Nur Zincir-Heywood,  Milios of Dalhousie University
https://www.cs.dal.ca/sites/default/files/technical_reports/CS-2010-06.pdf

R. Vaarandi, “Mining Event Logs with SLCT and Loghound,” in Proceedings
of the 2008 IEEE/IFIP Network Operations and Management
Symposium, April 2008, pp. 1071–1074.


How Does it Work?
_________________

Log lines are iteratively clustered, resulting in zero duplication of data, which helps ensure the algorithm stays memory efficent.
The main assumption is that multi-variable tokens are rare, thus token position is used as the main feature by which lines are clustered.

The prioirty of the cluster position is chosen based on the within cluster entropy of a given position. If a position is found to have
a sufficently high within cluster entropy, it is determined to be a variable.

Example cluster run
___________________

Log file

SSH user1 connect
SSH user2 connect
SSH user1 disconnect
SSH user3 connect
SSH user2 disconnect

The first pass of clustering is done by line length in order to make token positions comparable.

First cluster

All lines in our trivial example have a length of 3, so nothing really happens on the first cluster.

SSH user1 connect
SSH user2 connect
SSH user1 disconnect
SSH user3 connect
SSH user2 disconnect

Second Cluster

Token position 0 has the lowest entropy level (all tokens in position 0 are the same), so it is chosen as the first cluster position.
Again, nothing really changes.

cluster.indexes = [0]

SSH user1 connect
SSH user2 connect
SSH user1 disconnect
SSH user3 connect
SSH user2 disconnect

Third Cluster

Token position 2 has the next lowest entropy level (two options over five lines), now two clusters are created.

cluster1.indexes = [0,2]
SSH user1 connect
SSH user2 connect
SSH user3 connect


cluster2.indexes = [0,2]
SSH user1 disconnect
SSH user2 disconnect

On the next pass, the entropy level of the remaining position (position 1) is suffciently high that it satifies our condition to qualify as a variable.
We would then create our final clusters as there are no remaining cluster position candidates.

Cluster 1
Event: SSH * connect
Probability: SSH [(user1, 1), (user2,1), (user3,1)] connect

Cluster 2
Event: SSH * disconnect
Probability: SSH [(user1, 1), (user2, 1)] disconnect


