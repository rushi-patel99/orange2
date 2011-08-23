from plot.owplot3d import *
from plot.owplotgui import *
from plot.primitives import parse_obj

from Orange.preprocess.scaling import ScaleLinProjData3D
import orange
Discrete = orange.VarTypes.Discrete
Continuous = orange.VarTypes.Continuous

class OWLinProj3DPlot(OWPlot3D, ScaleLinProjData3D):
    def __init__(self, widget, parent=None, name='None'):
        OWPlot3D.__init__(self, parent)
        ScaleLinProjData3D.__init__(self)

        self.camera_fov = 50.
        self.show_axes = self.show_chassis = self.show_grid = False

        self.point_width = 6
        self.animate_plot = False
        self.animate_points = False
        self.antialias_plot = False
        self.antialias_points = False
        self.antialias_lines = False
        self.auto_adjust_performance = False
        self.show_filled_symbols = True
        self.use_antialiasing = True
        self.sendSelectionOnUpdate = False
        self.setCanvasBackground = self.setCanvasColor

        self._point_width_to_symbol_scale = 1.5

        self.gui = OWPlotGUI(self)

    def setData(self, data, subsetData=None, **args):
        ScaleLinProjData3D.setData(self, data, subsetData, **args)
        self.makeCurrent()
        self.state = PlotState.IDLE # Override for now, apparently this is modified by OWPlotGUI
        self.before_draw_callback = lambda: self.before_draw()

        cone_data = parse_obj('cone_hq.obj')
        vertices = []
        for v0, v1, v2, n0, n1, n2 in cone_data:
            vertices.extend([v0[0],v0[1],v0[2], n0[0],n0[1],n0[2],
                             v1[0],v1[1],v1[2], n1[0],n1[1],n1[2],
                             v2[0],v2[1],v2[2], n2[0],n2[1],n2[2]])

        self.cone_vao_id = GLuint(0)
        glGenVertexArrays(1, self.cone_vao_id)
        glBindVertexArray(self.cone_vao_id)

        vertex_buffer_id = glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, vertex_buffer_id)
        glBufferData(GL_ARRAY_BUFFER, numpy.array(vertices, 'f'), GL_STATIC_DRAW)

        vertex_size = (3+3)*4
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, vertex_size, c_void_p(0))
        glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, vertex_size, c_void_p(3*4))
        glEnableVertexAttribArray(0)
        glEnableVertexAttribArray(1)

        glBindVertexArray(0)
        glBindBuffer(GL_ARRAY_BUFFER, 0)

        self.cone_vao_id.num_vertices = len(vertices) / (vertex_size / 4)

        vertex_shader_source = '''#version 150
            in vec3 position;
            in vec3 normal;

            out vec4 color;

            uniform mat4 projection;
            uniform mat4 modelview;

            const vec3 light_direction = normalize(vec3(-0.7, 0.42, 0.21));

            void main(void)
            {
                gl_Position = projection * modelview * vec4(position, 1.);
                float diffuse = clamp(dot(light_direction, normalize((modelview * vec4(normal, 0.)).xyz)), 0., 1.);
                color = vec4(vec3(1., 1., 1.) * diffuse + 0.1, 1.);
            }
            '''

        fragment_shader_source = '''#version 150
            in vec4 color;

            void main(void)
            {
                gl_FragColor = color;
            }
            '''

        self.cone_shader = QtOpenGL.QGLShaderProgram()
        self.cone_shader.addShaderFromSourceCode(QtOpenGL.QGLShader.Vertex, vertex_shader_source)
        self.cone_shader.addShaderFromSourceCode(QtOpenGL.QGLShader.Fragment, fragment_shader_source)

        self.cone_shader.bindAttributeLocation('position', 0)
        self.cone_shader.bindAttributeLocation('normal', 1)

        if not self.cone_shader.link():
            print('Failed to link cone shader!')

    def before_draw(self):
        modelview = QMatrix4x4()
        modelview.lookAt(
            QVector3D(self.camera[0]*self.camera_distance,
                      self.camera[1]*self.camera_distance,
                      self.camera[2]*self.camera_distance),
            QVector3D(0, 0, 0),
            QVector3D(0, 1, 0))
        self.modelview = modelview

        glEnable(GL_DEPTH_TEST)
        glDisable(GL_BLEND)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        glMultMatrixd(numpy.array(self.projection.data(), dtype=float))
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        glMultMatrixd(numpy.array(self.modelview.data(), dtype=float))

        if self.showAnchors:
            for anchor in self.anchor_data:
                x, y, z, label = anchor

                direction = QVector3D(x, y, z)
                up = QVector3D(0, 1, 0)
                right = QVector3D.crossProduct(direction, up).normalized()
                up = QVector3D.crossProduct(right, direction)
                rotation = QMatrix4x4()
                rotation.setColumn(0, QVector4D(right, 0))
                rotation.setColumn(1, QVector4D(up, 0))
                rotation.setColumn(2, QVector4D(direction, 0))

                self.cone_shader.bind()
                self.cone_shader.setUniformValue('projection', self.projection)
                modelview = QMatrix4x4(self.modelview)
                modelview.translate(x, y, z)
                modelview = modelview * rotation
                modelview.rotate(-90, 1, 0, 0)
                modelview.translate(0, -0.02, 0)
                modelview.scale(-0.02, -0.02, -0.02)
                self.cone_shader.setUniformValue('modelview', modelview)

                glBindVertexArray(self.cone_vao_id)
                glDrawArrays(GL_TRIANGLES, 0, self.cone_vao_id.num_vertices)
                glBindVertexArray(0)

                self.cone_shader.release()

                glColor4f(0, 0, 0, 1)
                self.renderText(x*1.2, y*1.2, z*1.2, label)

                glBegin(GL_LINES)
                glVertex3f(0, 0, 0)
                glVertex3f(x, y, z)
                glEnd()

        self._draw_value_lines()

    def _draw_value_lines(self):
        if self.showValueLines:
            for line in self.value_lines:
                x, y, z, xn, yn, zn, color = line
                glColor3f(*color)
                glBegin(GL_LINES)
                glVertex3f(x, y, z)
                glVertex3f(x+self.valueLineLength*xn,
                           y+self.valueLineLength*yn,
                           z+self.valueLineLength*zn)
                glEnd()

    def updateData(self, labels=None, setAnchors=0, **args):
        self.clear()
        self.value_lines = []

        if not self.have_data or len(labels) < 3:
            self.anchor_data = []
            self.updateGL()
            return

        if setAnchors:
            self.setAnchors(args.get('XAnchors'), args.get('YAnchors'), args.get('ZAnchors'), labels)

        indices = [self.attribute_name_index[anchor[3]] for anchor in self.anchor_data]
        valid_data = self.getValidList(indices)
        trans_proj_data = self.create_projection_as_numeric_array(indices, validData=valid_data,
            scaleFactor=1.0, normalize=self.normalizeExamples, jitterSize=-1,
            useAnchorData=1, removeMissingData=0)
        if trans_proj_data == None:
            return

        proj_data = trans_proj_data.T
        proj_data[0:3] += 0.5 # Geometry shader offsets positions by -0.5; leave class unmodified
        if self.data_has_discrete_class:
            proj_data[3] = self.no_jittering_scaled_data[self.attribute_name_index[self.data_domain.classVar.name]]
        self.set_plot_data(proj_data, None)
        self.symbol_scale = self.point_width*self._point_width_to_symbol_scale
        self.hide_outside = False
        self.fade_outside = False

        color_index = symbol_index = size_index = label_index = -1
        color_discrete = False
        x_discrete = self.data_domain[self.anchor_data[0][3]].varType == Discrete
        y_discrete = self.data_domain[self.anchor_data[1][3]].varType == Discrete
        z_discrete = self.data_domain[self.anchor_data[2][3]].varType == Discrete

        if self.data_has_discrete_class:
            self.discPalette.setNumberOfColors(len(self.dataDomain.classVar.values))

        use_different_symbols = self.useDifferentSymbols and self.data_has_discrete_class and\
            len(self.data_domain.classVar.values) < len(Symbol)

        if use_different_symbols:
            symbol_index = 3
            num_symbols_used = len(self.data_domain.classVar.values)
        else:
            num_symbols_used = -1

        if self.useDifferentColors and self.data_has_discrete_class:
            color_discrete = True
            color_index = 3

        colors = []
        if color_discrete:
            for i in range(len(self.data_domain.classVar.values)):
                c = self.discPalette[i]
                colors.append([c.red()/255., c.green()/255., c.blue()/255.])

        self.set_shown_attributes_indices(0, 1, 2, color_index, symbol_index, size_index, label_index,
                                          colors, num_symbols_used,
                                          x_discrete, y_discrete, z_discrete,
                                          self.jitter_size, self.jitter_continuous,
                                          numpy.array([1., 1., 1.]), numpy.array([0., 0., 0.]))

        x_positions = proj_data[0]-0.5
        y_positions = proj_data[1]-0.5
        z_positions = proj_data[2]-0.5
        XAnchors = [anchor[0] for anchor in self.anchor_data]
        YAnchors = [anchor[1] for anchor in self.anchor_data]
        ZAnchors = [anchor[2] for anchor in self.anchor_data]
        data_size = len(self.raw_data)

        for i in range(data_size):
            if not valid_data[i]:
                continue
            if self.useDifferentColors:
                color = self.discPalette.getRGB(self.original_data[self.data_class_index][i])
            else:
                color = (0, 0, 0)

            len_anchor_data = len(self.anchor_data)
            x = array([x_positions[i]] * len_anchor_data)
            y = array([y_positions[i]] * len_anchor_data)
            z = array([z_positions[i]] * len_anchor_data)
            dists = numpy.sqrt((XAnchors - x)**2 + (YAnchors - y)**2 + (ZAnchors - z)**2)
            x_directions = 0.03 * (XAnchors - x) / dists
            y_directions = 0.03 * (YAnchors - y) / dists
            z_directions = 0.03 * (ZAnchors - z) / dists
            example_values = [self.no_jittering_scaled_data[attr_ind, i] for attr_ind in indices]

            for j in range(len_anchor_data):
                self.value_lines.append([x_positions[i], y_positions[i], z_positions[i],
                                         x_directions[j]*example_values[j],
                                         y_directions[j]*example_values[j],
                                         z_directions[j]*example_values[j],
                                         color])

        self.updateGL()

    def updateGraph(self, attrList=None, setAnchors=0, insideColors=None, **args):
        print('updateGraph')

    def setCanvasColor(self, c):
        pass

    def color(self, role, group=None):
        if group:
            return self.palette().color(group, role)
        else:
            return self.palette().color(role)

    def set_palette(self, palette):
        self.updateGL()

    def getSelectionsAsExampleTables(self, attrList, useAnchorData=1, addProjectedPositions=0):
        return (None, None)

    def removeAllSelections(self):
        pass

    def update_point_size(self):
        self.symbol_scale = self.point_width*self._point_width_to_symbol_scale
        self.updateGL()

    def update_alpha_value(self):
        self.updateGL()

    def replot(self):
        pass