import collections

VAR_TOKEN = "*HVRY%"


class Cluster(object):
  """Keeps track of a cluster of logfile lines.

  Args:
    lines: the lines (as lists) of the words represented by the cluster
    indexes: the set of token positions by which this set of lines have
      been clustered
    length: Total number of tokens in the line
  """
  def __init__(self, lines, indexes=None, length=None):
    self.lines = lines
    self.indexes = indexes or set()
    self.size = float(len(lines))
    self.length = length or len(lines[0])

  def __repr__(self):
    return 'lines: {}\nindexes: {}\nsize: {}\nlen: {}\n'.format(self.lines, self.indexes, self.size, self.length)


def cluster_lines(lines, prev_clusters=None, threshold=0.9):
  """Main Clustering function.
    Takes a list of lines, and returns a cluster. Lines are clustered by token
    positions with a uniquenes ratio below our threshold. Uniqueness is measured by
    the ratio between number of unique tokens in the position and the number of lines
    in the current cluster.

    We are able to incorporate old clusters by clustering with previously discovered
    events, ex: "SSH $TOKEN_VAR Connect" where a $TOKEN_VAR denotes a variable. If a variable token is
    discovered, we assume it to be a cluster, thus we set the threshold very high.
    We prefer false identification of clusters in the short term, with more accuracy
    as time goes on.

  Args:
    lines: A list of line strings,
    prev_clusters: A map of length of line as an int to a list of previously "discovered"
        events.
    threshold: a float between 0 and 1 used to determine if a position is a
        cluster point (constant) or a variable.
  Returns:
    A list of dicts containing:
      "event": abstracted event line. Ex "SSH $TOKEN_VAR connect"
      "size": number of lines the cluster represents
      "length": length of the lines
      "var_tree": A tree of nested dicts containing all of the possible variable
          combinations
  """

  # The first level of clustering occurs by length. The assumption is made that multi-token
  # variables are rare. Because we cluster by length, we can then use token position as a
  # reliable cluster point
  cluster_candidates = cluster_lines_by_len(lines, prev_clusters=prev_clusters)
  final_clusters = {}

  # We iteratively cluster the lines while there is still the potential for a new cluster
  # position/token
  while cluster_candidates:
    next_clusters = []

    # We check the cluster for token position which meets our requirements for a cluster point
    # If found, the cluster is queued for future subclustering. Otherwise, it is converted into
    # a final cluster form, which includes some analysis variable trees.
    for cluster in cluster_candidates:
      candidate_position = find_cluster_position(cluster, threshold)
      if candidate_position is not None:
        next_clusters.extend(create_new_clusters(cluster, candidate_position))
      else:
        event, event_data = create_final_cluster(cluster)
        final_clusters[event] = event_data
    cluster_candidates = next_clusters
  return final_clusters


def cluster_lines_by_len(lines, prev_clusters=None):
  """Takes lines and clusters them by their length.
    Converts the lines from strings to a list of tokens.

  Args:
    lines: List of lines as strings
    prev_clusters: previously clustered lines (represented as ex: ssh *HVRY% connect)
      clustered by line length.

  Returns:
    A list of Cluster objects
  """

  cluster_candidates = []
  lines_by_len = collections.defaultdict(list)

  for line in lines:
    if line:
      line = line.strip().split()
      lines_by_len[len(line)].append(line)

  for length, lines in lines_by_len.iteritems():
    if prev_clusters:
      lines += prev_clusters.get(length, [])
    cluster_candidates.append(Cluster(lines, length=length))

  return cluster_candidates


def find_cluster_position(cluster, threshold):
  """Finds the best cluster point for a given set of lines.

  Args:
    cluster: a Cluster object
    threshold: Max ratio of constant cutoff defined by postional cardinality over
      total lines in cluster

  Returns:
    An index of the token we should be using for the next cluster iteration
  """

  # If a cluster is only one line, there is nothing left do to do.
  if cluster.size == 1:
    cluster.indexes = set(range(cluster.length))
    return None

  cardinality_map = create_cardinality_map(cluster)
  candidate_positions = set(range(cluster.length)) - cluster.indexes
  min_cardinality = None
  candidate_position = None
  for position in candidate_positions:
    unique_tokens = cardinality_map.get(position)

    # Special case for inserting in old cluster data.
    if VAR_TOKEN in unique_tokens:
      continue

    cardinality = len(unique_tokens)
    if cardinality == 1:
      # FOR SOME REASON, cluster.indexes becoems shared over clusters.
      # We do a set union to return a new set.
      cluster.indexes = cluster.indexes.union(set([position]))
      continue

    if not min_cardinality or min_cardinality > cardinality:
      # TODO REFINE THIS AND EXPERIMENT!
      # Right now, the threshold between a variable and constant term
      # Is the ratio of:
      #   number of unique terms in the position
      #   number of lines in this cluster.
      # It is effectively the measure of entropy within a token position.
      # As the clusters continue to refine themselves,
      # variable tokens should become increasingly apparent.
      if (cardinality / cluster.size) < threshold:
        # We found a cluster candidiate
        min_cardinality = cardinality
        candidate_position = position

  return candidate_position


def create_cardinality_map(cluster):
  """Takes a cluster object and creates a map of token positions to the
    list of unqiue tokens which appear in that position.

  Args:
    cluster: A cluster object.

  Returns:
    A cardinality map. Aka a map of token positions to the set of tokens in that position.
  """

  cardinalities = collections.defaultdict(set)
  for line in cluster.lines:
    for position in xrange(cluster.length):
      cardinalities[position].add(line[position])
  return cardinalities


def create_new_clusters(cluster, candidate_position):
  """Takes a cluster and sub clusters it by the tokens in the given position.

  Args:
    cluster: A cluster object
    candidate_position: the position in the token list we are clustering on.

  Returns:
    A list of (sub) cluster objects.
  """

  new_cluster = collections.defaultdict(list)
  for line in cluster.lines:
    new_cluster[line[candidate_position]].append(line)

  indexes = set([candidate_position]).union(cluster.indexes)
  return [Cluster(lines, indexes=indexes) for lines in new_cluster.values()]


def create_final_cluster(cluster):
  """Takes in a cluster and converts it to its "final" form.

  The final form is a dictionary which maps an event line eg. "SSH $TOKEN connect"
  to a tree of its possible variables.

  Args:
    cluster: A cluster object.

  Returns:
    A dictionary mapping the "event" to its "event data".

    event:
      "SSH *HVRY% connect" where "*HVRY%" is a place holder for a variable.
    event data:
        vars: A tree of variable combinations and counts.
        total_lines: count of total lines in the cluster.
        line_len: number of tokens in a given line.
  """

  example_line = cluster.lines[0]
  event = ''
  var_tree = {}
  if not cluster.indexes:
    event = ' '.join(example_line)
  else:
    line_positions = range(cluster.length)
    var_positions = set(line_positions) - set(cluster.indexes)
    # First, strip out the "variables" from a line to create the event.
    for position in line_positions:
      if position in var_positions:
        token = VAR_TOKEN
      else:
        token = example_line[position]

      if position == 0:
        event += token
      else:
        event += ' ' + token

    # Now iterate over all lines, to find the var probabilities.
    for line in cluster.lines:
      # reset to root
      cur_tree = var_tree
      for var_position in var_positions:
        entry = cur_tree.get(line[var_position], {})
        entry['count'] = entry.get('count', 0) + 1
        cur_tree[line[var_position]] = entry

        children = entry.get('children', {})
        cur_tree = entry['children'] = children

  event_data = {
      'vars': var_tree,
      'total_lines': cluster.size,
      'line_len': cluster.length
  }
  return event, event_data


def clusters_to_tree(clusters):
  """Converts clusters to trees for string matching.

  Converts a list of events (ssh *HVRY% connect, ssh *HVRY% disconnect)
  to a tree (ssh -> *HVRY -> [connect, disconnect])

  Args:
    clusters: a dictionary of events to event data.

  Returns:
    A tree (nested dictionaries) of all the possible events
    Top level key is the length of the line.
  """

  tree = {}
  for event in clusters.keys():
    length = clusters[event]['line_len']
    branch = tree[length] = tree.get(length, {})
    for token in event.split():
      entry = branch[token] = branch.get(token, {})
      branch = entry
  return tree


def find_event_in_tree(tree, line):
  """Uses an event tree to map a log line to its corresponding event.

  Args:
    tree: Event tree which is a nest dictionary of lines to their possible next
        tokens. Root of the tree is line length.
    line: Raw log line from the file.

  Returns:
    An event if discovered or None.
  """

  tokens = line.split()
  length = len(tokens)
  branch = tree.get(length)
  clustered_line = ""

  for i in xrange(length):
    token = tokens[i]
    next_branch = branch.get(token)
    if next_branch is None:
      if VAR_TOKEN in branch.keys():
        next_branch = branch.get(VAR_TOKEN)
        token = VAR_TOKEN
      else:
        return None
    if i == 0:
      clustered_line = token
    else:
      clustered_line += " " + token
    branch = next_branch
  return clustered_line


def extract_vars_from_line(line, event):
  """Extracts the variables from a given line.

  Args:
    line: a raw log line.
    event: a clustered event.

  Returns:
    A list of variables.
  """

  variables = []
  line = line.split()
  for i, token in enumerate(event.split()):
    if token == VAR_TOKEN:
      variables.append(line[i])
  return variables


def calculate_prob(event, variables, clusters, total_lines):
  """Given an event and its variables, returns its probability profile.

  Args:
    event: A string of an event entry, eg. SSH *HVRY% connect
    variables: A list of variables ordered by their appearance in the line.
    clusters: A map of events to event data.
    total_lines: total lines processed for this log file.

  Returns:
    a tuple of event prob and event with var prob
  """

  entry = clusters.get(event)

  if not entry:
    # We add one to the total number of lines, and make the prob one out of this set.
    # This is the only place we are incrementally updating the size of the set.
    # probably should be doing it elsewhere, but the plan is to only update set size on
    # incremental update.
    return 1.0 / (total_lines + 1), None
  else:
    var_tree = entry['vars']
    event_prob = entry['total_lines'] / total_lines
    if variables:
      level = var_tree.get(variables[0])
      count = level['count']
      children = level['children']
      i = 1
      count = 1
      while children and i < len(variables):
        level = children.get(variables[i])
        if not level:
          break
        count = level['count']
        children = level['children']
        i += 1
      var_prob = count / entry['total_lines']
    else:
      var_prob = None

  return event_prob, var_prob
