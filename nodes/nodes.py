"""nodes: An easy-to-use graph-oriented programming model for Python.

"""
import collections
import copy
import types

Settable     = 0x1
Serializable = 0x2
Saved        = Settable | Serializable
Overlayable  = 0x4

class Graph(object):
    """A directed, acyclic graph of nodes.

    """
    def __init__(self):
        self.nodes = {}
        self.activeNode = None                         # The active node during a computation.
        self.activeGraphContext = None                 # The currently active context.
        self.rootGraphLayer = GraphLayer()             # The top level graph layer.
        self.activeGraphLayer = self.rootGraphLayer    # The currently active graph layer.
        self.activeOverlay = self.rootGraphLayer._activeOverlay

    def onNodeChanged(self, node):
        outputs = node.outputs
        for output in outputs:
            if output.valid:
                output._flags &= ~output.VALID
                self.onNodeChanged(output)

    def lookupNode(self, graphInstanceMethod, args, create=True):
        """Returns the Node underlying the given object and its method
        as called with the specified arguments.

        """
        key = (graphInstanceMethod.graphObject, graphInstanceMethod.name) + args
        if key not in self.nodes and create:
            self.nodes[key] = Node(graphInstanceMethod.graphObject, graphInstanceMethod.graphMethod, args)
        return self.nodes.get(key)

    def _lookupNode(self, graphInstanceMethod, args=(), create=True):
        raise NotImplementedError()

    def _createNode(self, graphInstanceMethod, args=()):
        raise NotImplementedError()

    def isComputing(self):
        """Returns True if the graph is currently computing a value,
        False otherwise.

        The impact of computation is that no other graph modifications
        (sets and overlays, that is) can be updated.

        """
        # The test is simple at the moment: if a node is active,
        # we're computing.
        #
        return self.activeNode

    def _isComputing(self):
        raise NotImplementedError()

    def getValue(self, node, graphContext=None):
        """Returns the value of the node, recalculating if necessary,
        honoring any active graph context.

        """
        # TODO: Consider rewriting as a visitor or context.
        #
        outputNode, self.activeNode = self.activeNode, node
        try:
            if outputNode:
                outputNode.addInput(node)
                node.addOutput(outputNode)
            return node.getValue()
        finally:
            self.activeNode = outputNode

    def _getValue(self, graphInstanceMethod, args=()):
        raise NotImplementedError()

    def _calculateValue(self, graphInstanceMethod, args=()):
        raise NotImplementedError()

    def setValue(self, node, value):
        """Sets for value of a node, and raises an exception
        if the node is not settable.

        """
        # get the node from the layer
        # 
        if self.isComputing():
            raise RuntimeError("You cannot set a node during graph evaluation.")
        node.setValue(value)

    def _setValue(self, graphInstanceMethod, value, args=()):
        raise NotImplementedError()

    def clearSet(self, node):
        """Clears the current node if it has been set.

        Raises an exception if the node has not been
        set.

        Note that clearing a value is not the same as
        forcing its clearing its memoized, calculated
        value, if one is present.

        """
        if self.isComputing():
            raise RuntimeError("You cannot clear a set value during graph evaluation.")
        node.clearSet()

    def _clearValue(self, graphInstanceMethod, args):
        raise NotImplementedError()

    def overlayValue(self, node, value):
        """Adds a overlay to the active graph context and immediately applies it to the node.

        """
        if self.isComputing():
            raise RuntimeError("You cannot overlay a node during graph evaluation.")
        if not self.activeGraphContext:
            raise RuntimeError("You cannot overlay a node outside a graph context.")
        self.activeGraphContext.overlayValue(node, value)

    def _overlayValue(self, graphInstanceMethod, args, value):
        raise NotImplementedError()

    def clearOverlay(self, node):
        """Clears an overlay previously set in the active graph context.

        """
        if self.isComputing():
            raise RuntimeError("You cannot clear a overlay during graph evaluation.")
        if not self.activeGraphContext:
            raise RuntimeError("You cannot clear a overlay outside a graph context.")
        self.activeGraphContext.clearOverlay(node)

    def _clearOverlay(self, graphInstanceMethod, args=()):
        raise NotImplementedError()

class GraphVisitor(object):
    """Visits a hierarchy of graph nodes in depth first order.

    Assumes the node has been evaluated at least once so
    that its inputs have been updated.  Even this is imperfect
    and is one downside of the dynamic apporach.

    """
    # TODO: I only support node visitation at the moment, so
    #       I'm avoiding overhead of the double-dispatch here,
    #       indeed, it would probably get a getattr() call not a 
    #       method call on the graph object.
    #
    def visit(self, node):
        yetToVisit = [node]
        while yetToVisit:
            yetToVisit.extend(self.visitNode(yetToVisit.pop(0)))

    def visitNode(self, node):
        """Visits a node and returns a list of additional nodes
        to visit.

        """
        raise NotImplementedError()

class _GraphVisitor(object):

    def __init__(self, graph):
        self._graph = graph

    def _visitOutputs(self, node, graphContext):
        outputs = node.outputs
        while outputs:
            output = outputs.pop(0)
            self._visit(output, graphContext)
            outputs.extend(output.outputs)

    def _visitInputs(self, node, graphContext):
        inputs = node.inputs
        while inputs:
            input = inputs.pop(0)
            self._visit(input, graphContext)
            inputs.extend(input.inputs)

    def _visit(self, node):
        raise NotImeplementedError()

# TODO: Split collections of overlays from the contexts.
# TODO: Decouple this from the graph, making graph a paramter to __init__?
# TODO: Store nodes in contexts (not as some global that gets 
#       special handling if a context is active).

class GraphContext(object):
    """A graph context is collection of temporary node changes
    (called overlays) that can be applied and unapplied
    without modifying the global node settings or overlays in
    higher-level contexts.

    The user creates a graph context by using the object
    as a context and setting overlays on the nodes he wishes
    to modify within that context.

    The general syntax is:

        with GraphContext() as c:
            o.X.overlayValue(...)
            o.Y.overlayValue(...)

            ...

    once created, a context can be applied similarly:

        with c:
            ...

    additional overlays applied when using the context in the
    second case are not saved to the context.

    One can also create a GraphContext that inherits nodes
    from a parent context.

    """
    def __init__(self, graph=None, parentGraphContext=None):
        self._graph = graph or _graph
        self._parentGraphContext = parentGraphContext
        self._nodes = {}
        self._overlays = {}           # Node overlays by node.
        self._state = {}              # Node values by node.
        self._applied = set()         # Nodes whose overlays in this context have been applied.
        self._removed = set()         # Nodes set at a higher level but cleared here.
        self._populating = True

    def _lookupNode(self, graphInstanceMethod, args, create=True):
        key = (graphInstanceMethod.graphObject, graphInstanceMethod.name) + args
        if key not in self._nodes and create:
            self._nodes[key] = self.createNode(graphInstanceMethod, args)
        return self._nodes.get(key)

    def _createNode(self, graphInstanceMethod, args):
        return Node(graphInstanceMethod.graphObject, graphInstanceMethod.name, args, self)

    def _getValue(self, node):
        # TODO: This is a test implementation with node's internals exposed.
        if not node._isValid:
            node._value = node.graphMethod(node.graphObject, *node.args)
        return node._value

    def _setValue(self, node, value):
        self._invalidateNodeOutputs(node)
        node._value = value
        node._isValid = True
        node._isSet = True

    def _clearValue(self, node):
        self._invalidateNode(node)

    def _invalidateNode(self, node):
        self._invalidateNodeOutputs(node)
        node._isSet = False
        node._isValid = False
        node._value = None

    def _invalidateNodeOutputs(self, node):
        for output in node.outputs:
            if output._isSet:
                continue
            self._invalidateNode(output)

    def addOverlay(self, node, value):
        """Adds a new overlay to the graph context, but does not apply it to the node.

        If an existing overlay is already set, replaces its value.

        """
        self._overlays[node] = value
        if node in self._removed:
            self._removed.remove(node)

    def removeOverlay(self, node):
        """Removes an overlay from the graph context, but does not unapply it from
        the node.

        """
        self._removed.add(node)
        if node in self._overlays:
            del self._overlays[node]

    def overlayValue(self, node, value):
        """Adds an overlay to the graph context and immediately applies it to
        the node.

        """
        self.addOverlay(node, value)
        self.applyOverlay(node)

    def applyOverlay(self, node):
        """Applies an overlay to a node, stashing away any existing
        overlays (from another graph context) that were inherited so we can
        reapply them later.

        """
        # FIXME: State handling is a bit too coupled here, I think.
        if node.isOverlaid() and node not in self._applied:
            self._state[node] = node.getOverlay()
        node.overlayValue(self.getOverlay(node))
        self._applied.add(node)

    def clearOverlay(self, node):
        """Removes the overlay from the node, restoring old state,
        and, if this overlay was in the current graph context, also
        removes it from the overlay data.

        """
        if self.isOverlaid(node):
            if node in self._state:
                node.overlayValue(self._state[node])
                del self._state[node]
            else:
                node.clearOverlay()
            if self._populating:
                self.removeOverlay(node)
            self._applied.remove(node)

    def isOverlaid(self, node):
        """Return True if an overlay in this graph context (or any of its parents)
        is active on the node.

        """
        return node in self._applied

    def hasOverlay(self, node, includeParent=True):
        """Returns True if an overlay exists for the node in this
        graph context.

        """
        if node in self._removed:
            return False
        if node in self._overlays:
            return True
        if includeParent and self._parentGraphContext:
            return self._parentGraphContext.hasOverlay(node)
        return False

    def allOverlays(self, includeParent=True):
        """Returns a list of all overlays presnet in the graph context.

        If includeParent is True (the default) also includes
        parent overlays that haven't been set specifically
        in this graph context.

        """
        if not includeParent or not self._parentGraphContext:
            return self._overlays.copy()
        overlays = self._parentGraphContext.allOverlays()
        overlays.update(self._overlays)
        for removed in self._removed:
            overlays.pop(removed)
        return overlays

    def getOverlay(self, node, includeParent=True):
        """Returns the overlay for the specified
        node as it exists within this graph context.

        Raises an exception if an overlay for the node does
        not exist.

        """
        return self.allOverlays(includeParent=includeParent)[node]

    def __enter__(self):
        """Enter the graph context, activating any overlays it contains.

        Note that overlays always override already-applied overlays, so
        if overlays have been applied in a higher graph context, stash those
        away to be restored when we exit the current context.

        """
        self.activeParentGraphContext, self._graph.activeGraphContext = self._graph.activeGraphContext, self
        if not self._populating:
            self._graph.activeGraphContext = GraphContext(parentGraphContext=self._graph.activeGraphContext)
        for node in self._graph.activeGraphContext.allOverlays():
            self._graph.activeGraphContext.applyOverlay(node)
        return self

    def __exit__(self, *args):
        """Exit the graph context and remove any applied overlays.

        """
        if self._populating:
            self._populating = False
        for node in self._graph.activeGraphContext.allOverlays():
            self._graph.activeGraphContext.clearOverlay(node)
        self._graph.activeGraphContext = self.activeParentGraphContext

class GraphOverlay(object):
    """An GraphOverlay is a collection of node changes that can
    be applied and unapplied by the user.

    """
    def __init__(self, graph, graphLayer):
        """Creates an overlay for the specified layer.

        """
        self._graph = graph
        self._graphLayer = graphLayer
        self._overlays = {}

    def addOverlay(self, node, value):
        raise NotImplementedError()

    def removeOverlay(self, node):
        raise NotImplementedError()

    def __enter__(self):
        self._previousOverlay, self._graph.activeOverlay = self._graph.activeOverlay, self
        self._previousLayerOverlay, self._graphLayer._activeOverlay = self._graphLayer._activeOverlay, self
        return

    def __exit__(self, *args):
        return

def graphOverlay():
    return GraphOverlay(_graph, _graph.activeGraphLayer)

def graphVisit(node, visitor):
    """Visits the specified node.  The visitor is a callable
    that accepts a node and returns a list of additional
    nodes to visit, if any.

    Each node is guaranteed to be visited at most one
    time in order to prevent cycles, regardless of how
    many times it is in the node list returned by the visitor.

    """
    nodesVisited = set()
    def visit(node):
        if node in nodesVisited:
            return []
        nodesVisited.add(node)
        for n in visitor(node):
            visit(n)
    visit(node)

class GraphLayer(object):
    """A hierarchy of nodes and node states.

    """
    def __init__(self, graph=None, parentGraphLayer=None):
        self._graph = graph
        self._parentGraphLayer = parentGraphLayer
        self._nodes = {}
        self._rootOverlay = GraphOverlay(self._graph, self)
        self._activeOverlay = self._rootOverlay
        self._overlayStack = collections.defaultdict(lambda: [])
        self._activeStack = []

    def nodeKey(self, graphInstanceMethod, args):
        return (graphInstanceMethod.graphObject, graphInstanceMethod.name) + args

    def lookupNode(self, graphInstanceMethod, args, create=True):
        key = self.nodeKey(graphInstanceMethod, args)
        if key not in self._nodes and create:
            node = self.createNode(graphInstanceMethod, args)
        return self._nodes.get(key)

    def createNode(self, graphInstanceMethod, args):
        key = self.nodeKey(graphInstanceMethod, args)
        if key in self._nodes:
            raise RuntimeError("That node already exists in this layer.")
        node = self._nodes[key] = self._newNode(graphInstanceMethod, args)
        return node

    def _newNode(self, graphInstanceMethod, args):
        """Creates and returns a new Node that references this
        layer.

        """
        return Node(graphInstanceMethod.graphObject, graphInstanceMethod.graphMethod, args, self)

    def setValue(self, graphInstanceMethod, value, args):
        key = self.lookupNode(graphInstanceMethod, args)
        node._value = value
        node._flags |= node.SET

    def applyOverlay(self, node, overlay):
        if node.isValid or node.set:
            self._overlayStack[node].append([node._value, node._flags])
        node._flags &= ~(node.VALID|node.SET)
        node._value = overlay
        #        for output in node.outputs:
        #    output.invalidate()
        #
        # TODO: Invalidate node - or graph

    def removeNodeOverlay(self, node):
        """Removes only the most recent overlay."""
        if not node in self._overlayStack:
            raise RuntimeError("No overlay has been applied to that node in this graph layer.")
        node._value, node._flags = self._overlayStack[node].pop()
        # TODO: Invalidate grpah.

    def __enter__(self):
        # We save the state to a stack (not just a pair of variables) because the
        # user might do something like:
        #
        # with i:
        #     ...
        #     with j:
        #         ...
        #         with i:   <-- Without a stack this would overwrite the prior history,
        #
        self._activeStack.append((self._graph.activeGraphLayer, self._graph.activeOverlay))
        self._graph.activeGraphLayer = self
        self._graph.activeOverlay = self.rootOverlay
        return self

    def __exit__(self):
        self._graph.activeGraphLayer, self._graph.activeOverlay = self._activeStack.pop()

def graphLayer(parentGraphLayer=None):
    parentGraphLayer = parentGraphLayer or _graph.activeGraphLayer
    return GraphLayer(parentGraphLayer._graph, parentGraphLayer=parentGraphLayer)

class GraphMethod(object):
    """An unbound graph-enabled method.

    Holds state and settings for all instances of an object
    containing this method.

    """

    def __init__(self, method, name, flags=0, delegateTo=None):
        """Creates a new graph method, which lifts a regular method
        into a version that supports graph-based dependency
        tracking and other graph features.

        When an instance of a class inheriting from GraphObject
        is created, any  methods defined on it are
        bounded to the instance as GraphInstanceMethods.

        By default all GraphInstanceMethods are read-only
        (i.e., cannot be set or overlaid, and always derive values
        via their underlying method).

        Use flags to modify this default behavior.

        Flags available:
            * Settable      The value can be directly set by a user.
            * Serializable  The value (whether set or computed) will be
                            extracted as part of object state.
            * Saved         Equivalent to setting both Settable and Serializable.


        delegateTo is optional and if provided must be set to
        can be set to a callable.  In that case, when the value of the
        GraphInstanceMethod is set by a user (via a setValue operation),
        a call to the callable is made instead, passing in the value
        the user specified.

        The delegate must return a list of NodeChange objects,
        each of which is a mapping between a GraphInstanceMethod (and
        any arguments specific to its node) and the value it will be set to.

        """
        self.method = method
        self.name = name
        self.flags = flags
        self.delegateTo = delegateTo

    def isSettable(self):
        """Returns True if a bound instance of the
        can be set by a user, or False otherwise.

        """
        return self.flags & Settable

    def isOverlayable(self):
        return self.isSettable or self.flags & Overlayable

    def isChangeable(self):
        return self.isSettable() or self.isOverlayable() or self.delegatesChanges()

    def isSerializable(self):
        """Returns True if the value of a bound instance of the
        should be included as part of the object's state
        during serialization routines.  Otherwise returns False.

        This would also typically mean that the graph method
        is settable as well, though this is not strictly
        required.

        """
        return self.flags & Serializable

    def isSaved(self):
        """Equivalent to setting the Settable and Serializable
        flags on the graph method.

        The reasoning is that we have no desire to save purely
        computed values, so we only save settable ones that
        are also serializable.

        Returns True if both flaas are set, or False otherwise.
        """
        return self.flags & Saved == Saved

    def delegatesChanges(self):
        """Returns True if changes to this method are handled
        by a delegate that itself is responsible for
        returning a list of the actual desired changes.

        """
        return self.delegateTo is not None

    def __call__(self, graphObject, *args):
        """A short-cut to calling the underlying method with the supplied
        arguments.

        """
        return self.method(graphObject, *args)

# TODO: Move the value setting stuff out of Node.  Let's just create
#       a Node per context, and have graph or context be responsible
#       for tracking value changes, inputs/outputs, validity and
#       the like.  For one thing, this means we don't have to provide
#       an interface for a user to set a Node's value directly, which is 
#       rife with issues, while also allowing a user to inspect a node's
#       value or other state.
#       

class Node(object):
    """A node on the graph.

    A node is uniquely identified by

        (graphObject, graphMethod, args)

    and a GraphInstanceMethod maps to one or more nodes differentiated
    by the arguments used to call it.

    """
    INVALID  = 0x0000
    VALID    = 0x0001   # Applies to node computation only.
    SET      = 0x0002
    OVERLAID = 0x0004

    def __init__(self, graphObject, graphMethod, args=(), graphContext=None):
        """Creates a new node on the graph.

        Fundamentally a node represents a value that is either
        calculated or directly specified by a user.

        """
        self._graphObject = graphObject
        self._graphMethod = graphMethod
        self._args = args
        self._graphContext = graphContext
        self._outputs = set()
        self._inputs = set()

        # TODO: This is a hack.  If I set a value and then
        #       overlay its value, for example, there's no immediate reason
        #       I shouldn't be able to merely restore the old value.
        #       For now this state is maintaineded here, which works 
        #       on the assumption that setting a node is a context-independent
        #       operation but overlaying it is temporary and graph context-
        #       specific.
        #
        self._isOverlaid = False
        self._isSet = False
        self._isCalced = False

        # TODO:  I'm maintaining values for overlays, sets, and calcs 
        #        each in a separate namespace, which is necessary 
        #        if we wish to reavoid calculating when, for example,
        #        overlays are set, but maintaining them within the node 
        #        itself is questionable.  I need to rethink this.
        #
        self._overlaidValue = None
        self._setValue = None
        self._calcedValue = None

        # TODO:  New stuff for movement to contexts as storage layer.
        #        Also using flags; the individual bools are getting hard to manage.
        #        Value is now set by the graph, which makes it easier to
        #        track.

        self._value = None
        self._flags = self.INVALID

    @property
    def valid(self):
        return self._flags & self.VALID

    @property
    def set(self):
        return self._flags & self.SET

    @property
    def overlaid(self):
        return self._flags & self.OVERLAID

    @property
    def fixed(self):
        return self._flags & (self.SET|self.OVERLAID)

    @property
    def outputs(self):
        return self._outputs

    @property
    def inputs(self):
        return self._inputs

    @property
    def value(self):
        return self._value

    def addInput(self, inputNode):
        """Informs the node of an input dependency, which indicates
        the node requires the input node's value to complete
        its own computation.

        Input nodes are only used when a node has not been set
        directly (via a setValue or overlayValue operation).

        """
        self._inputs.add(inputNode)

    def addOutput(self, outputNode):
        """Informs the node of a new output, that is, a node
        that depends on the current node for its own value.

        When the current node is invalidated it invalidates
        its outputs as well.

        """
        self._outputs.add(outputNode)

    def removeInput(self, inputNode):
        """Removes the specified node from the list of required
        inputs, or does nothing if the node is not a known
        input.

        """
        if node in self._inputs:
            self._inputs.remove(inputNode)

    def removeOutput(self, outputNode):
        """Removes the output from the list of node outputs, or
        does nothing if the node is not a known output.

        """
        if node in self._outputs:
            self._outputs.remove(outputNode)

    def getValue(self):
        """Return the node's current value, recalculating if necessary.

        If the current value is valid, there is no need to recalculate it.

        """
        # TODO: See comment above regarding the split of these 
        #       tests and the variables used to store values based on 
        #       how a node was fixed/calced.  Short story: this will
        #       be rewritten.
        #
        if self.isOverlaid():
            return self._overlaidValue
        if self.isSet():
            return self._setValue
        if not self.isCalced():
            self.calcValue()
        return self._calcedValue

    def calcValue(self):
        """(Re)calculates the value of this node by calling
        its underlying method on graph, and updating the
        stored value and status of the calculation
        accordingly.

        Note that this method will force a recalculation
        even if the current calculation is valid.  The result
        of the recalculation should in that case be exactly
        the same as the result already calculated.  If it
        is not then either the method is not pure or there
        is an issue with the graph.

        """
        self._calcedValue = self._graphMethod(self._graphObject, *self._args)
        self._isCalced = True

    def _invalidateCalc(self):
        """Removes any calculated value, forcing a recalculation
        the next time the node has no set or overlaid value.

        """
        self._invalidateOutputCalcs()
        self._isCalced = False
        self._calcedValue = False

    def _invalidateOutputCalcs(self):
        """Invalidates any outputs that were dependent on this
        node as part of a calculation.

        """
        for output in self._outputs:
            output._invalidateCalc()

    def setValue(self, value):
        """Sets a specific value on the node.

        Setting a value invalidates known outputs that are not set
        themselves.

        """
        if not self._graphMethod.isSettable():
            raise RuntimeError("You cannot set a read-only node.")
        self._invalidateOutputCalcs()
        self._setValue = value
        self._isSet = True

    def _setValue(self, value):
        raise NotImplementedError()

    def clearSet(self):
        """Clears a previously set value on the node, if
        any.

        """
        if not self._graphMethod.isSettable():
            raise RuntimeError("You cannot clear a read-only node.")
        if not self.isSet():
            return
        self._invalidateOutputCalcs()
        self._isSet = False
        self._setValue = None

    def _clearValue(self):
        raise NotImplementedError()

    def overlayValue(self, value):
        """Overlays the value of the node.  At this level a overlay
        is merely a value stored in a different namespace that
        nonetheless invalidates any output nodes.

        """
        # TODO: Perhaps optimize for _overlaidValue == value case.
        if not self._graphMethod.isOverlayable():
            raise RuntimeError("You cannot overlay this node.")
        self._invalidateOutputCalcs()
        self._overlaidValue = value
        self._isOverlaid = True

    def clearOverlay(self):
        """Clears the current overlay, if any, invalidating
        outputs if a overlay was actually cleared.

        """
        if not self._graphMethod.isOverlayable():
            raise RuntimeError("You cannot overlay this node, so certainly you can't clear any overlay!")
        if not self.isOverlaid():
            return
        self._invalidateOutputCalcs()
        self._isOverlaid = False
        self._overlaidValue = None

    def getOverlay(self):
        """Returns the value of the current overlay, if any, or
        raises an exception otherwise.

        """
        if not self.isOverlaid():
            raise RuntimeError("This node is not overlaid.")
        return self._overlaidValue

    def isValid(self):
        """Returns True if the node's value is current.

        """
        return self._isOverlaid or self._isSet or self._isCalced

    def isOverlaid(self):
        """Returns True if this node is overlaid, False otherwise.

        Overlays are independent of sets and calcs.

        """
        return self._isOverlaid

    def isSet(self):
        """Return True if this node was set to an explicit value.

        In that case it will no longer be recomputed or invalidated
        if its dependencies change.

        """
        return self._isSet

    def isCalced(self):
        """Return True if the value was calculated.

        """
        return self._isCalced

    # TODO: Move this out.  Let's make nodes totally dumb.
    #       All the know is their value and inputs and outputs.
    #       They don't actually expose methods (except for helpers)
    #       that modify their state.

    def invalidate(self):
        self._flags &= ~self.VALID
        for output in self.outputs:
            if output.valid:
                output.invalidate()

    def __repr__(self):
        return '<Node graphObject=%r;graphMethod=%s;args=%s>' % (
                self._graphObject,
                self._graphMethod,
                self._args
                )

    def __str__(self):
        return '<Node %s.%s(%s) isSet=%s;isOverlaid=%s;isCalced=%s>' % (
                self.graphObject.__class__.__name__,
                self.graphMethod.name,
                str(self.args),
                self.isSet(),
                self.isOverlaid(),
                self.isCalced()
                )

class NodeChange(object):
    """Encapsulates a pending change to a node.  Intended to be
    returned by delegates to indicate the nodes the delegate
    wants to change.

    (A delegate cannot changes these nodes directly as the
    delegate runs during graph computation.)

    """
    def __init__(self, graphInstanceMethod, value, *args):
        self.graphInstanceMethod = graphInstanceMethod
        self.value = value
        self.args = args

    @property
    def node(self):
        return _graph.lookupNode(self.graphInstanceMethod, self.args, create=True)

    def _toNode(self, graph, graphContext):
        return graph.lookupNode(self.graphInstanceMethod, self.args, graphContext, create=True)

class NodeReference(object):
    """A handle on the node details that are shared across
    all graph layers.

    """
    def __init__(self, graph, graphInstanceMethod, args):
        self._graph = graph
        self._graphInstanceMethod = graphInstanceMethod
        self._args = args

    def toNode(self, graphLayer):
        return self._graph._lookupNode(self._graphInstanceMethod, self._args, graphLayer=graphLayer, create=True)

class GraphInstanceMethod(object):
    """A GraphMethod  bound to an instance of its class.

    A GraphInstanceMethod provides the glue linking the user object
    and the graph.

    """
    def __init__(self, graphObject, graphMethod):
        self.graphObject = graphObject
        self.graphMethod = graphMethod

    @property
    def name(self):
        return self.graphMethod.name

    def node(self, *args):
        return _graph.lookupNode(self, args, create=True)

    def __call__(self, *args):
        return self.getValue(*args)

    def getValue(self, *args):
        """Returns the current value of underlying node based on the current
        graph state.

        """
        return _graph.getValue(self.node(*args))

    def _getValue(self, *args):
        return _graph._getValue(self, args)

    def setValue(self, value, *args):
        # TODO: Is this the right place for delegation, or should
        #       we do that within the node implementation?  I
        #       don't like it in Node, because a node doesn't know
        #       about the global graph state.  We could put it in
        #       a higher level (perhaps in _graph.setValue()) perhaps.
        #       There is a lot of coupling between all of these
        #       things but the code is simple enough it should be
        #       easy to refactor as needs demand.
        #
        if self.graphMethod.delegatesChanges():
            nodeChanges = self.graphMethod.delegateTo(self.graphObject, value, *args)
            for nodeChange in nodeChanges:
                _graph.setValue(nodeChange.node, nodeChange.value)
            return
        _graph.setValue(self.node(*args), value)

    def _setValue(self, value, *args):
        # TODO: Handle delegation in the graph.  Perhaps add a switch
        #       here to indicate whether to delegate or not?
        _graph._setValue(self, value, args)

    def clearSet(self, *args):
        _graph.clearSet(self.node(*args))

    def _clearValue(self, *args):
        _graph._clearValue(self, args)

    def overlayValue(self, value, *args):
        _graph.overlayValue(self.node(*args), value)

    def _overlayValue(self, value, *args):
        _graph._overlayValue(self, value, args)

    def clearOverlay(self, *args):
        _graph.clearOverlay(self.node(*args))

    def _clearOverlay(self, *args):
        _graph._clearOverlay(self, args)

    def isSet(self, *args):
        return self.node(*args).isSet()

    def isOverlaid(self, *args):
        return self.node(*args).isOverlaid()

class GraphType(type):
    """Metaclass responsible for creating on-graph objects.

    """
    def __init__(cls, name, bases, attrs):
        if name != 'GraphObject' and '__init__' in cls.__dict__:
            raise RuntimeError("GraphObject {} is not permitted to override __init__".format(name))

        for k,v in attrs.items():
            if isinstance(v, GraphMethod) and v.name != k:
                v_ = copy.copy(v)
                v_.name = k
                v_.flags = v.flags
                setattr(cls, k, v_)

        type.__init__(cls, name, bases, attrs)

        graphMethods = []
        for k in dir(cls):
            v = getattr(cls, k)
            if isinstance(v, GraphMethod):
                graphMethods.append(v)
        cls._graphMethods = graphMethods
        cls._savedGraphMethods = [v for v in graphMethods if v.isSaved()]

class GraphObject(object):
    """A graph-enabled object.

    """
    __metaclass__ = GraphType

    def __setattr__(self, name, value):
        v = getattr(self, name)
        if isinstance(v, GraphInstanceMethod):
            v.setValue(value)
            return
        object.__setattr__(self, name, value)

    def __init__(self, **kwargs):
        for k in dir(self):
            v = getattr(self, k)
            if isinstance(v, GraphMethod):
                object.__setattr__(self, k, GraphInstanceMethod(self, getattr(self,k)))
        for k,v in kwargs.items():
            attr = getattr(self, k)
            if not isinstance(attr, GraphInstanceMethod):
                raise RuntimeError("Not a GraphInstanceMethod: %s" % k)
            self.__setattr__(attr.graphMethod.name, v)

    def toDict(self):
        """Returns a dictionary of name/value pairs for all saved methods.

        """
        # TODO: Flesh this out a bit: deep toDict, including settable nodes, perhaps, etc.
        return dict((k.name, getattr(self, k.name)()) for k in self._savedGraphMethods)

def graphMethod(funcOrFlags=0, delegateTo=None):
    """Declare a GraphObject method as on-graph.

    Use as a decorator, for example:

        class Example(GraphObject):

            @graphMethod
            def X(self):
                return self.Y()

            @graphMethod(Settable)
            def Y(self):
                return ...

    """
    if type(funcOrFlags) == types.FunctionType:
        return GraphMethod(funcOrFlags, funcOrFlags.__name__)
    def wrap(f):
        return GraphMethod(f, f.__name__, funcOrFlags, delegateTo=delegateTo)
    return wrap

_graph = Graph()

# TODO: Add a node garbage collector (perhaps weakref).
# TODO: Add multithreading support.
# TODO: Add database storage support.
# TODO: Add subscriptions.
# TODO: Productionize for large-scale use (perhaps with CPython).
# TODO: Integrate with AMPS.
