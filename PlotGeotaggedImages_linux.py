import os,sys
import shutil
import requests

sys.path.append("/usr/local/bin/qgis")

from qgis.core import *
from qgis.gui import *
import qgis.utils
from qgis.PyQt import QtGui
from qgis.gui import QgsLayerTreeMapCanvasBridge, QgsMapCanvas
from qgis.analysis import QgsNativeAlgorithms

from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtXml import *


#sys.path.append('/usr/local/pkgs/qgis-3.18.3-py39h9ccb726_5/share/qgis/python/plugins')
sys.path.append('/usr/local/pkgs/qgis-3.18.3-py39hcd9851b_6/share/qgis/python/plugins')

import processing
from processing.core.Processing import Processing   

# http://geospatialpython.com/2015/05/geolocating-photos-in-qgis.html?m=1

'''
Adds an integer field for Index
INPUT:points layer
OUTPUT:points layer with new field 'row_num'
'''
def add_index(vlayer):
    #Add a new field for serial number
    pr = vlayer.dataProvider()
    pr.addAttributes([QgsField("row_num",  QVariant.Int)])
    pr.addAttributes([QgsField("arrow_len",  QVariant.Int)])
    vlayer.updateFields()
    
    #Fill the field with serial number
    context = QgsExpressionContext()
    context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(vlayer))
    
    with edit(vlayer):
        row_num=1
        for f in vlayer.getFeatures():
            context.setFeature(f)
            f['row_num'] = row_num
            f['arrow_len'] = 10
            vlayer.updateFeature(f)
            row_num=row_num+1
    print('Added index field ')

'''
Convert a folder of Geotagged photos to point shapefile
INPUT:photos_path
OUTPUT:shpfile_points_path
'''
def import_geotags(photos_path,shpfile_points_path):
    Processing.initialize()
    QgsApplication.processingRegistry().addProvider(QgsNativeAlgorithms())
    feedback = QgsProcessingFeedback()     
     
    processing.run(
        'native:importphotos',
        { 'FOLDER' : photos_path, 'OUTPUT' : shpfile_points_path, 'RECURSIVE' : False },
        feedback=feedback
        )['OUTPUT']

    layer = QgsVectorLayer(shpfile_points_path, "Photos_GPS", "ogr")
    add_index(layer)
    # print('import_geotags::', feedback)

'''
Project vector layer
INPUT:shpfile_points_path
OUTPUT:Projected vector layer. 
Projection is WebMercator --> required for Google Satellite image as basemap
'''
def project_shpfile(shpfile_points_path):
    Processing.initialize()
    QgsApplication.processingRegistry().addProvider(QgsNativeAlgorithms())
    feedback = QgsProcessingFeedback()     

    shp_projected=processing.run(
        'native:reprojectlayer',
        { 'INPUT' : shpfile_points_path, 'OPERATION' : '+proj=pipeline +step +proj=unitconvert +xy_in=deg +xy_out=rad +step +proj=webmerc +lat_0=0 +lon_0=0 +x_0=0 +y_0=0 +ellps=WGS84', 'OUTPUT' : 'TEMPORARY_OUTPUT', 'TARGET_CRS' : QgsCoordinateReferenceSystem('EPSG:3857') },
        feedback=feedback
        )['OUTPUT']

    # print('project_shpfile::', feedback)
    return shp_projected

'''
Prepares map layers required 
OUTPUT:Points vector layer, Google basemap both in same coordinate system CRS:3857
'''
def prep_layers(photos_path):
    service_url = "https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}"
    service_uri = "type=xyz&zmin=0&zmax=21&url="+requests.utils.quote(service_url)
    rlayer = QgsRasterLayer(service_uri, "Google Hybrid", "wms")
        
    if not rlayer.isValid():
        print('Invalid layer')
    
    # photos_path = r'C:\SAI\IIIT_2021\UW\Hans\test'
    shpfile_points_path =os.path.join(photos_path,'Geotagged_Photos.shp')
    
    import_geotags(photos_path,shpfile_points_path)
    vlayer=project_shpfile(shpfile_points_path)
    
    if not vlayer.isValid():
      print("Layer failed to load!")
              
    return  vlayer,rlayer

def set_symbology(vlayer_point,vlayer):
    #Set Symbology of Points
    vlayer_point.renderer().symbol().setSize(2)
    vlayer_point.renderer().symbol().setColor(QColor(136,245,27))
    
    #Set Symbology of Points as arrows with direction and labels
    vlayer.loadNamedStyle('symbology.qml')
    vlayer.triggerRepaint()

#Initiliaze Standalone Application
qgisApp = QgsApplication([], True)
qgisApp.setPrefixPath(r"/usr/local/bin/qgis", True) #/usr/local/bin/qgis ,# C:\Program Files\QGIS 3.16
qgisApp.initQgis()

#Add a project to the  Standalone Application
project = QgsProject.instance()

#Access the convas of the map
canvas = QgsMapCanvas()
canvas.resize(QSize(1280,720)) # You can adjust this values to alter image dimensions
canvas.show()

project.write('GeotaggedPhotos_project.qgz')


def prepareMap(photos_path): # Arrange layers
    
    vlayer,tms_layer =prep_layers(photos_path)
    #Add map layers 
    project.addMapLayer(tms_layer)
    project.addMapLayer(vlayer)
    
    #Add a temporary layer to show location of camera
    vlayer.selectAll()
    vlayer_point = processing.run("native:saveselectedfeatures", {'INPUT': vlayer, 'OUTPUT': 'memory:'})['OUTPUT']
    vlayer.removeSelection()
    project.addMapLayer(vlayer_point)
    
    set_symbology(vlayer_point,vlayer)
    vlayer.triggerRepaint()
    vlayer_point.triggerRepaint()
    canvas.setLayers( [vlayer_point,vlayer,tms_layer] )
    canvas.setExtent(vlayer.extent())
    my_extent = QgsRectangle(vlayer.extent())
    my_extent.scale(1.4) #Expand the envelope to cover a little more area 
    canvas.setExtent(my_extent)
    
    canvas.mapCanvasRefreshed.connect( exportMap2PNG )

'''
Exports the map to a PNG image
'''
def exportMap2PNG(): # Save the map as a PNG
    canvas.saveAsImage("Geotagged_Photos.png" )
    print ("Map with layer exported!")
    qgisApp.exitQgis()
    qgisApp.exit() 

def main():
    args = sys.argv[1:]   
    photos_path=args[0]
    prepareMap(photos_path) 
    qgisApp.exec_()
    
if __name__ == '__main__':
    main()   
