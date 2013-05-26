"""nodes: An easy-to-use graph-oriented object model for Python.

"""
import collections
import copy
import types

Settable     = 0x1
Serializable = 0x2
Saved        = Settable | Serializable
Overlayable  = 0x4

class Graph(object):
    """The core graph plumbing; essentially the controller and
    global runtime state.

    Most of the node values and state are context-specific.
    The high-level Graph interface is merely a front-end
    to the context-specific hooks, with context determined
    by state.

    That is, a graph is essentially a set of layered storage
    values, with the root layer having 'special' status
    as the global context in which values are set and
    retrieved by default, and that drive persistent changes.

    The subsidiary contexts are used only for temporary changes.

    """
    # TODO: Split overlays and layers, but have layers maintain their
    #       own overlays.  This way we can more easily distinguish
    #       between the two, but also apply the concepts independently.
    #
    #       So, a graph layer becomes a place to set and retrieve
    #       node values.  In order to create a node you must do
    #       so in a graph layer.
    #
    #       Further, a graph layer can be a child of another graph
    #       layer, in which the parent layer's nodes are also available
    #       to it.  The entire tree is treated as a single node store (yes? no?).
    #       
    #       A graph overlay, on the other hand, is a set of node
    #       values that can be applied and unapplied without overwriting
    #       the node's 'permanent' underlying value.  
    #
    #       An 'active' layer or 'active' overlay is the current layer
    #       in a stack of layers (or overlay, respectively) used by the 
    #       graph and layers themselves when calculating (or otherwise 
    #       getting) the state and value of nodes.
    #       
    #       Both graph layers and graph overlays are also Python
    #       contexts; objects of the classes themselves maintain
    #       values and state, and the graph and layer/overlay context
    #       are the means through which the user 'activates' the
    #       corresponding layer or context.
    #
    #       We will have helper functions that both create and make
    #       active layers and contexts, simplying file for the library
    #       user.
    #       
    def __init__(self):
        self.nodes = {}
        self.activeNode = None                                  # The active node during a computation.
        self.activeGraphContext = None                          # The currently active context.
        self.rootGraphLayer = GraphLayer()                      # The top level graph layer.
        self.activeGraphLayer = self.rootGraphLayer             # The currently active graph layer.

    def lookupNode(self, graphInstanceMethod, args, create=True):
        """Returns the Node underlying the given object and its method
        as called with the specified arguments.

        """
        key = (graphInstanceMethod.graphObject, graphInstanceMethod.name) + args
        if key not in self.nodes and create:
            self.nodes[key] = Node(graphInstanceMethod.graphObject, graphInstanceMethod.graphMethod, args)
        return self.nodes.get(key)

    def _lookupNode(self, graphInstanceMethod, args, graphLayer=None, create=True):
        currentLayer = graphLayer or self.activeGraphLayer
        node = None
        while currentLayer:
            node = graphLayer.lookupNode(graphInstanceMethod, args, create=False)
            if node:
                break
            currentLayer = graphLayer.parentLayer
        if not node:
            node = graphLayer.lookupNode(graphInstanceMethod, args, create=True)
        node = graphContext._lookupNode(graphInstanceMethod, args, create=create)
        if not node and create:
            return self._createNode(graphInstanceMethod, args, graphContext)
        return node

    def _createNode(self, graphInstanceMethod, args, graphLayer):
        return graphContext._createNode(graphInstanceMethod, args)

    def _invalidateNode(self, node):
        self._invalidateNodeOutputs(node)
        node._isValid = False
        node._isSet = False

    def _invalidateNodeOutputs(self, node):
        for outputNode in node.outputs:
            if outputNode._isSet:
                continue
            self._invalidateNode(outputNode)

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
        return self.activeNode

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

    def _getValue(self, node, graphContext):
        return graphContext._getValue(node)

    def setValue(self, node, value):
        """Sets for value of a node, and raises an exception
        if the node is not settable.

        """
        # get the node from the layer
        # 
        if self.isComputing():
            raise RuntimeError("You cannot set a node during graph evaluation.")
        node.setValue(value)

    def _setValue(self, node, value, graphContext):
        if not isComputing():
            raise RuntimeError("You cannot set a node during graph evaluation.")
        graphContext._setValue(node, value)

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

    def _clearValue(self, node, graphContext):
        graphContext._clearValue(node)

    # TODO: Is an overlay really just a graph context that overrides a 
    #       higher level graoh context, with no need for special 'overlay' 
    #       values per se, the only differentiation being at the client
    #       interface level?
    #
    #       If this is the case, the the context needs not know about
    #       overlays.
    #
    #       But here's a use case:  
    #           top context has nodes A -> B; and C
    #           enter a new context:
    #               set B
    #               now, in the context, I ask for A.
    #               A doesn't exist in context, so is created
    #               A is computed
    #               now have two contexts:
    #                   top (A, B, C)
    #                   child (A, B)
    #
    #           exit the context:
    #               save nodes until context is out of scope
    #               clean up nodes when it is
    #
    #           what about C.  an in child context, as for C.
    #           C is not in context.  I could create it.
    #           But because it doesn't use anything that has
    #           changed in the context, the top value is still
    #           valid, so why shouldn't I use that?
    #           
    #           But how do I know this?  I can ask for C's inputs,
    #           and if any of these inputs is in the current context
    #           and invalid, i create and compute C.
    #
    #           If not, I use parent context's C.  But what if the contexts
    #           are highly nested?  
    #
    #       Let's assume we fix this up.  Then an 'overlay' is really just a
    #       setting that requires a specific context.
    #
    #       EXCEPT, there is still a problem.  What if I overlay in the top
    #       context?  Where does the old value go?
    #   
    #       One option is to enforce this in the Graph interface so that
    #       overlay operations either always implicitly define a new 
    #       context, OR prevent overlay is the active context == the
    #       graph's root context.
    #
    #       I think this will work ...
    #

    def overlayValue(self, node, value):
        """Adds a overlay to the active graph context and immediately applies it to the node.

        """
        if self.isComputing():
            raise RuntimeError("You cannot overlay a node during graph evaluation.")
        if not self.activeGraphContext:
            raise RuntimeError("You cannot overlay a node outside a graph context.")
        self.activeGraphContext.overlayValue(node, value)

    def _overlayValue(self, node, value, graphContext):
        graphContext._overlayValue(node, value)

    def applyOverlay(self, node, value, graphLayer):
        graphLayer = graphLayer or self._activeGraphLayer
        graphLayer.applyOverlay(node, value)

    def clearOverlay(self, node):
        """Clears an overlay previously set in the active graph context.

        """
        if self.isComputing():
            raise RuntimeError("You cannot clear a overlay during graph evaluation.")
        if not self.activeGraphContext:
            raise RuntimeError("You cannot clear a overlay outside a graph context.")
        self.activeGraphContext.clearOverlay(node)

    def _clearOverlay(self, node, graphContext):
        graphContext._clearOverlay(node)

class Overlay(object):

    def __init__(self, value):
        self._value = value

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
        # TODO: At the moment contexts reference parents, and don't copy their
        #       nodes.  This means a node cleared or added to a parent context
        #       will affect the child context.  I'm not sure this is good.
        #       It also means maintaining additional state in every context,
        #       namely, the nodes that are overlaid in a higher level context
        #       but that have been cleared in the current context.
        #
        #       Bottom line, I'll probably change this to do a copy
        #       of the parent overlays at context creation time, and then
        #       break that relationship.
        #
        self._graph = graph or _graph
        self._parentGraphContext = parentGraphContext
        self._nodes = {}
        self._overlays = {}           # Node overlays by node.
        self._state = {}              # Node values by node.
        self._applied = set()         # Nodes whose overlays in this context have been applied.
        self._removed = set()         # Nodes set at a higher level but cleared here.
        self._populating = True

    def _lookupNode(self, graphInstanceMethod, args, create=True):
        # Search parent contexts, or local context only.
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
        # If the node was overlaid in this graph context, we need to restore any
        # existing overlays that may have been applied outside of this
        # graph context. 
        #
        # If we're populating, remove it from the context as well.  
        #
        # TODO: I'm refactoring this now that I have a better handle 
        #       on the interactions between contexts.  I wanted to get 
        #       something out people could use first, kinks and all.
        #
        if self.isOverlaid(node):
            # If the node had a value that we stashed away, restore it.
            # Otherwise, clear it.
            if node in self._state:
                # TODO: I re-overlay here - which kind of seems wrong in that the
                #       original overlay was never really "removed," but at present
                #       will work for our cases.  This also has the side-effect 
                #       of invalidating the parent node, which again is something
                #       we want because the node was invalidated when we applied
                #       our overlays.  Nevertheless, it'd be nice to merely preserve
                #       the original state and avoid the recalculation of the 
                #       parent nodes if they really don't need to be recalculated.
                #       I believe this should be straight-forward once we have sets
                #       fully isolated.
                #
                #       Also we don't clear our existing overlay here, relying on
                #       fact that overlaying the node will essentially do that for us.
                #
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
        # TODO: Differentiate between "with GraphContext() as c" and "with c":
        #       the latter should not update the context when new overlays are
        #       added or removed.
        #
        self.activeParentGraphContext, self._graph.activeGraphContext = self._graph.activeGraphContext, self

        # If we're not populating, create a dummy context to collect overlay changes that
        # we don't want to store to the the actual context.
        #
        # I'm probably going to break this into two contexts at some point.
        #
        if not self._populating:
            self._graph.activeGraphContext = GraphContext(parentGraphContext=self._graph.activeGraphContext)
        for node in self._graph.activeGraphContext.allOverlays():
            self._graph.activeGraphContext.applyOverlay(node)
        return self

    def __exit__(self, *args):
        """Exit the graph context and remove any applied overlays.

        """
        # We only populate the first time we enter the context.
        #
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
        self._overlaidNodes = set()

    @property
    def overlays(self):
        return self._overlays
    # TODO: Add add/remove/etc., basically code that was in GraphContext

def graphOverlay():
    # MEH - Should we pass in graph, even if technically the layer 
    #       already has this?  Wondering if serialization parts will
    #       will need this, so for now passing it in.
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
        self._overlayStack = {}

    def lookupNode(self, graphInstanceMethod, args, create=True):
        """Looks for a matching Node in this layer or any of its
        ancestors.

        If a node is returned its graphLayer will indicate
        where it was found.

        If create is True and no node exists, the node will be
        created in the this layer.

        """
        key = (graphInstanceMethod.graphObject, graphInstanceMethod.name) + args
        graphLayer = self
        while graphLayer:
            if key in graphLayer._nodes:
                return graphLayer._nodes.get(key)
            graphLayer = graphLayer._parentGraphLayer
        if create:
            self._nodes[key] = self.createNode(graphInstanceMethod, args)
        return self._nodes.get(key)

    def createNode(self, graphInstanceMethod, args):
        """Creates a new node linked to this graph layer.

        """
        return Node(graphInstanceMethod.graphObject, graphInstanceMethod.graphMethod, args, self)

    def getNodeValue(self, node):
        return node.getValue()

    def setNodeValue(self, node, value):
        node.setValue(value)

    def clearNodeValue(self, node):
        node.clearValue()

    def applyNodeOverlay(self, node, overlay):
        overlays = self._overlayStack.get(node, [])
        if node.isValid():
            self._overlayStack.append([node._value, node.isValid(), node.isSet(), node.isOverlaid()])
        # TODO: This is getting hard to track; I'll switch to flags.
        node._isValid = False
        node._isSet = False
        node._isOverlaid = True
        node.value = overlay
        # FIXME: Invalidate node - or graph
        raise

    def removeNodeOverlay(self, node):
        """Removes only the most recent overlay."""
        overlays = self._overlayStack.get(node)
        if not overlays:
            return
        value, isValid, isSet, isOverlaid = overlays[-1]
        node._isValid = isValid
        node._isSet = isSet
        node._isOverlaid = isOverlaid
        node._value = value
        # FIXME: Invalidate node - or graph
        raise

    # Used when we actually enter the layer.
    def __enter__(self):
        self._activeParentGraphLayer = self._graph.activeGraphLayer
        self._graph.activeGraphLayer = self
        return self

    def __exit__(self):
        self._graph.activeGraphLayer = self._activeParentGraphLayer

def graphLayer(parentGraphLayer=None):
    return GraphLayer(_graph, parentGraphLayer=parentGraphLayer)

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
        self._isValid = False
        self._value = None

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

    @property
    def outputs(self):
        return self._outputs

    @property
    def inputs(self):
        return self._inputs

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

    def _getValue(Self):
        if not self._isValid:
            self._calcValue()
        return self._value

    def _calcValue(self):    # Calculate the node.
        self._value = self._graphMethod(self._graphObject, *self._args)

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

    def _toNode(self, *args):
        return _graph._lookupNode(self, args, create=True)

    def __call__(self, *args):
        return self.getValue(*args)

    def getValue(self, *args):
        """Returns the current value of underlying node based on the current
        graph state.

        """
        return _graph.getValue(self.node(*args))

    def _getValue(self, *args):
        return _graph._getValue(self._toNode(*args))

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
        _graph._setValue(self._toNode(*args))

    def clearSet(self, *args):
        _graph.clearSet(self.node(*args))

    def _clearValue(self, *args):
        _graph._clearValue(self._toNode(*args))

    def overlayValue(self, value, *args):
        _graph.overlayValue(self.node(*args), value)

    def _overlayValue(self, value, *args):
        _graph._overlayValue(self._toNode(*args), value)

    def clearOverlay(self, *args):
        _graph.clearOverlay(self.node(*args))

    def _clearOverlay(self, *args):
        _graph._clearOverlay(self._toNode(*args))

    def isSet(self, *args):
        return self.node(*args).isSet()

    def isOverlaid(self, *args):
        return self.node(*args).isOverlaid()

class GraphType(type):
    """Metaclass responsible for creating on-graph objects.

    """
    def __init__(cls, name, bases, attrs):
        for k,v in attrs.items():
            if isinstance(v, GraphMethod) and v.name != k:
                v_ = copy.copy(v)
                v_.name = k
                v_.flags = v.flags
                setattr(cls, k, v_)

        type.__init__(cls, name, bases, attrs)

        if name != 'GraphObject' and '__init__' in cls.__dict__:
            raise RuntimeError("GraphObject {} is not permitted to override __init__".format(name))

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
