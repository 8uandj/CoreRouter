# Physical edge-list source review (22 November 2026)

The evaluated `TopologyManager` in `src/orchestration/jo_vdpr/topology.py` defines 10 Vietnam, 14 NSFNET and 23 GEANT2 nodes. For these named substrates, it creates adjacency by thresholding coordinate-derived pair latency; the resulting evaluated graphs are complete. The current sparse GAT–MLP sensitivity uses a symmetric nearest-neighbour graph computed from latency. Neither provides a verified physical backbone edge list.

Candidate sources checked:

| Source | What it offers | Why it cannot yet be substituted into the evaluated model |
|---|---|---|
| [Internet Topology Zoo dataset](https://topology-zoo.org/dataset.html) and its [Nsfnet GraphML source](https://github.com/sk2/topologyzoo/blob/master/sources/Nsfnet.graphml) | Public, documented graph records; the Nsfnet file labels itself as a 2011 network snapshot. | A 2011 network snapshot is not automatically the historical 14-node 1991 NSFNET benchmark represented by the current node list. Its node names, graph layer and edges need explicit mapping and verification. |
| [NSFNET backbone historical map](https://nsf.net/projects/backbone) | A 1991 map showing backbone sites and circuits. | It is a historical map rather than a machine-readable edge list matched to the current ordered node IDs. |
| [Knowledge-Defined Networking datasets](https://knowledgedefinednetworking.org/) | Lists a 14-node NSFNet and a 24-node GEANT2 dataset. | The GEANT2 node count differs from the 23-node substrate used in this paper; no one-to-one node mapping has been established. |

Before a physical-edge experiment, pin a source revision and license, record the original node and edge list with SHA-256, map every source node to exactly one modeled node (or document exclusions), verify connectedness and edge count, and keep the latency/resource assumptions separate from the measured connectivity. A graph constructed by nearest neighbours or an unmatched external topology must not be labelled as a physical-edge result.
