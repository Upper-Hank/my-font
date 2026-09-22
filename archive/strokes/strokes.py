"""Persistent, reviewable stroke drafts; the source glyph is always immutable."""
import copy
import math
import re
import shutil
import uuid
from pathlib import Path
import cv2
import numpy as np
from .common import OutputDirectory, digest, read_json, write_json
from .storage import data_dir
from .project import resolve_glyph, load_live, sample_library
from .adjust import adjustment_options
from .stroke_geometry import (SIZE, source_raster, references, reference_candidates, geometry_candidates,
                              mask_url, encode_mask, decode_mask, component_names, contour_commands)
from .trace import write_preview_svg

ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}')
COLORS = [(65,113,224),(210,81,70),(46,154,125),(165,98,197),(218,143,35),(43,154,189)]


def source(work, identifier):
    if not isinstance(identifier,str) or len(identifier.split('/')) != 2 or not all(ID.fullmatch(p) for p in identifier.split('/')):
        raise ValueError('字形编号无效。')
    if identifier in load_live(work).get('archived_sample',[]):
        raise ValueError('请先从回收站恢复字形。')
    run, sample = identifier.split('/')
    row = resolve_glyph(work, {'run':run,'sample_id':sample,'char':''}, adjusted=False)
    if row['status'] != 'review' or not row['commands']:
        raise ValueError('请选择一个可用字形。')
    return row, data_dir(work,'glyphs') / run / sample / 'strokes.json'


def fingerprint(row):
    return digest({'char':row['char'],'commands':row['commands']})


def make_stroke(mask, label, group='', origin='geometry', review=True):
    return {'id':uuid.uuid4().hex[:12],'name':label,'group':group,'origin':origin,'review':review,
            'mask':encode_mask(mask),'visible':True,'transform':{'x':0,'y':0,'scale':1}}


def payload(work, identifier, row, document=None):
    ink, frame = source_raster(row)
    result = {'sample':identifier,'char':row['char'],'original':mask_url(ink), 'frame':frame,
              'has_reference':row['char'] in references(), 'size':SIZE}
    if document:
        result.update({key:value for key,value in document.items() if key not in ('strokes','undo','source_hash')})
        result['can_undo'] = bool(document.get('undo'))
        result['strokes'] = [{**{k:v for k,v in s.items() if k!='mask'},'image':mask_url(decode_mask(s['mask']),COLORS[i%len(COLORS)])} for i,s in enumerate(document['strokes'])]
        masks = [decode_mask(s['mask']) for s in document['strokes'] if s['visible']]
        union = np.maximum.reduce(masks) if masks else np.zeros_like(ink)
        result['unassigned_pixels'] = int(np.count_nonzero(ink & (1-union)))
    else:
        result.update({'strokes':[],'revision':0,'can_undo':False})
    return result


def get_strokes(work, identifier):
    row,path = source(work,identifier)
    document = read_json(path) if path.is_file() else None
    if document and document['source_hash'] != fingerprint(row):
        raise ValueError('原字形发生变化，请重新生成笔画候选。')
    return payload(work,identifier,row,document)


def persist(path, document):
    temporary = path.with_suffix('.json.tmp')
    write_json(temporary,document)
    temporary.replace(path)


def generate(work, identifier, revision):
    row,path = source(work,identifier)
    old = read_json(path) if path.is_file() else None
    if revision != (old['revision'] if old else 0):
        raise ValueError('笔画已在其他页面修改，请刷新后重试。')
    ink,frame = source_raster(row)
    if not ink.any():
        raise ValueError('没有可拆分墨迹。')
    ref = references().get(row['char'])
    strokes, notes = [], []
    if ref:
        geometrical, support, skeleton = reference_candidates(ink,ref)
        groups = component_names(ref)
        for index, mask in enumerate(geometrical):
            if np.count_nonzero(mask) < 3:
                notes.append(f'参考第 {index+1} 笔没有匹配到墨迹，未强行生成。')
                continue
            origin = 'structure+geometry'
            stroke = make_stroke(mask,f'第 {index+1} 笔',groups[index] if index<len(groups) else '',origin,True)
            stroke['reference_index'] = index+1
            stroke['match_score'] = round(support[index],2)
            strokes.append(stroke)
        notes.append('参考结构仅辅助匹配，编号与部件归属均需人工确认；未自动确认任何笔画。')
    else:
        candidates,skeleton = geometry_candidates(ink)
        for index,mask in enumerate(candidates):
            strokes.append(make_stroke(mask,f'候选 {index+1}',origin='connected-ink'))
        notes.append('该字符没有标准结构参考。独立墨迹不一定是一笔，请人工拆分或合并。')
    union = np.maximum.reduce([decode_mask(s['mask']) for s in strokes]) if strokes else np.zeros_like(ink)
    remainder = ink & (1-union)
    if remainder.any():
        strokes.append(make_stroke(remainder,'未分配墨迹',origin='residual'))
    if len(strokes)>128:
        raise ValueError('碎片过多，请先清理字形。')
    document = {'schema':1,'source_hash':fingerprint(row),'revision':(old['revision'] if old else 0)+1,
                'frame':frame,'strokes':strokes,'notes':notes,'method':'structure+geometry' if ref else 'connected-ink',
                'expected_count':len(ref['medians']) if ref else None,'undo':[]}
    persist(path,document)
    return payload(work,identifier,row,document)


def finite(value, low, high):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not low<=value<=high:
        raise ValueError('编辑参数超出范围。')
    return value


def edit(work, identifier, revision, operation, args):
    row,path = source(work,identifier)
    if not path.is_file():
        raise ValueError('请先生成笔画候选。')
    document = read_json(path)
    if document['revision'] != revision or document['source_hash'] != fingerprint(row):
        raise ValueError('笔画已变化，请刷新后重试。')
    if not isinstance(args,dict):
        raise ValueError('编辑参数无效。')
    if operation == 'undo':
        if not document['undo']:
            raise ValueError('没有可撤销的编辑。')
        document['strokes'] = document['undo'].pop()
    else:
        ids = args.get('ids',[])
        if not isinstance(ids,list) or not ids or len(ids)>128 or any(not isinstance(s,str) for s in ids) or len(set(ids))!=len(ids):
            raise ValueError('请选择笔画。')
        chosen = [s for s in document['strokes'] if s['id'] in ids]
        if len(chosen)!=len(ids):
            raise ValueError('笔画不存在。')
        document['undo'] = (document['undo']+[copy.deepcopy(document['strokes'])])[-12:]
        if operation == 'merge':
            if len(chosen)<2:
                raise ValueError('至少选择两个笔画。')
            masks = [transformed_mask(s) for s in chosen]
            merged = make_stroke(np.maximum.reduce(masks),'合并笔画',origin='manual')
            document['strokes'] = [s for s in document['strokes'] if s['id'] not in ids]+[merged]
        elif operation == 'split':
            if len(chosen)!=1:
                raise ValueError('请选择一个笔画后拖出切分线。')
            points = args.get('points')
            if not isinstance(points,list) or len(points)!=2 or any(not isinstance(p,list) or len(p)!=2 for p in points):
                raise ValueError('请拖出一条切分线。')
            (x0,y0),(x1,y1) = [[finite(v,0,SIZE) for v in p] for p in points]
            norm = math.hypot(x1-x0,y1-y0)
            if norm<3:
                raise ValueError('切分线太短。')
            yy,xx = np.mgrid[:SIZE,:SIZE]
            side = ((xx-x0)*(y1-y0)-(yy-y0)*(x1-x0))/norm
            mask = transformed_mask(chosen[0])
            overlap = finite(args.get('overlap',1),0,12)
            parts = [mask*(side>=-overlap),mask*(side<=overlap)]
            if any(np.count_nonzero(p)<3 for p in parts):
                raise ValueError('切分线未穿过笔画。')
            document['strokes'] = [s for s in document['strokes'] if s['id'] not in ids]+[make_stroke(p,f'{chosen[0]["name"]} · {i+1}',chosen[0]['group'],'manual') for i,p in enumerate(parts)]
        elif operation in ('paint','erase'):
            if len(chosen)!=1:
                raise ValueError('请选择一个笔画。')
            points = args.get('points')
            if not isinstance(points,list) or not 1<=len(points)<=2048 or any(not isinstance(p,list) or len(p)!=2 for p in points):
                raise ValueError('画笔路径无效。')
            points = np.array([[finite(v,0,SIZE) for v in p] for p in points],np.int32)
            brush = int(finite(args.get('brush',5),1,40))
            mask = transformed_mask(chosen[0])
            color = 1 if operation=='paint' else 0
            cv2.polylines(mask,[points],False,color,brush)
            for point in (points[0],points[-1]):
                cv2.circle(mask,tuple(point),max(1,brush//2),color,-1)
            chosen[0].update(mask=encode_mask(mask),transform={'x':0,'y':0,'scale':1},origin='manual',review=True)
        elif operation == 'update':
            patch = args.get('patch',{})
            if not isinstance(patch,dict) or set(patch)-{'name','group','visible','review','transform'}:
                raise ValueError('笔画属性无效。')
            for key in ('name','group'):
                if key in patch and (not isinstance(patch[key],str) or len(patch[key])>40):
                    raise ValueError('名称最多 40 个字符。')
            for key in ('visible','review'):
                if key in patch and not isinstance(patch[key],bool):
                    raise ValueError('开关参数无效。')
            if 'transform' in patch:
                t=patch['transform']
                if not isinstance(t,dict) or set(t)!= {'x','y','scale'}:
                    raise ValueError('位置参数无效。')
                patch['transform']={'x':finite(t['x'],-128,128),'y':finite(t['y'],-128,128),'scale':finite(t['scale'],.25,3)}
            for stroke in chosen:
                if 'transform' in patch:
                    transformed_mask({**stroke, **patch})
                stroke.update(patch)
        else:
            raise ValueError('不支持的笔画操作。')
    if len(document['strokes'])>128:
        raise ValueError('最多保留 128 个笔画对象。')
    document['revision']+=1
    persist(path,document)
    return payload(work,identifier,row,document)


def transformed_mask(stroke):
    t=stroke['transform']
    mask=decode_mask(stroke['mask'])
    affine=np.array([[t['scale'],0,SIZE/2*(1-t['scale'])+t['x']],[0,t['scale'],SIZE/2*(1-t['scale'])+t['y']]],np.float32)
    # Merge/paint rasterization is bounded; do not silently crop an edited stroke.
    ys,xs=np.nonzero(mask)
    if len(xs):
        x=(xs-SIZE/2)*t['scale']+SIZE/2+t['x']; y=(ys-SIZE/2)*t['scale']+SIZE/2+t['y']
        if x.min()<0 or y.min()<0 or x.max()>=SIZE or y.max()>=SIZE:
            raise ValueError('笔画超出编辑框，请先移回框内再切分、合并或绘制。')
    return cv2.warpAffine(mask,affine,(SIZE,SIZE),flags=cv2.INTER_NEAREST)


def publish(work, identifier, revision):
    row,path=source(work,identifier)
    document=read_json(path)
    if document['revision']!=revision or document['source_hash']!=fingerprint(row):
        raise ValueError('笔画已变化，请刷新后重试。')
    if document.get('published_revision')==revision:
        return {'sample':document['published_sample'],'char':row['char']}
    chosen=[s for s in document['strokes'] if s['visible']]
    if not chosen or any(s['review'] for s in chosen):
        raise ValueError('请先确认所有保留的笔画，再生成新字形。')
    commands=[]
    for stroke in chosen:
        transformed_mask(stroke)  # Reject off-canvas ink instead of publishing an unseen result.
        commands.extend(contour_commands(decode_mask(stroke['mask']),document['frame'],stroke['transform']))
    if not commands:
        raise ValueError('笔画合成结果为空。')
    name='strokes-'+uuid.uuid4().hex[:12]
    destination=data_dir(work,'glyphs')/name
    with OutputDirectory(destination) as folder:
        assets=folder/'one'; assets.mkdir()
        source_folder=Path(row['run_folder'])/row['sample_id']
        for filename in ('gray.png','binary.png'):
            if (source_folder/filename).is_file():
                shutil.copyfile(source_folder/filename,assets/filename)
        left,top,side=document['frame']
        write_preview_svg(assets/'outline.svg',commands,(left,top-side,side,side))
        copied={**row,'commands':commands,'sample_id':'one','gray':'one/gray.png','stroke_source':identifier,
                'stroke_revision':revision,'adjustment':adjustment_options(load_live(work).get('adjustments',{}).get(identifier,row.get('adjustment')))}
        copied.pop('run_folder',None)
        write_json(folder/'run.json',{'schema':1,'run_id':name,'cell_mm':row['cell_mm'],'glyphs':[copied]})
    document['published_revision']=revision; document['published_sample']=f'{name}/one'
    persist(path,document)
    sample_library(work)
    return {'sample':f'{name}/one','char':row['char']}
