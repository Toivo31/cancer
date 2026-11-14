"""Checkpoint-aware setup for the simulator adapter without editing teammate-owned jev/."""
STEP = 2350
SHA256 = '22570c201a9e3d25dcdf7aa904770a568328e034ccb5ac89623784707a7323e8'


def backend(**options):
    from jev.birch import BirchBackend
    class HostedBirchBackend(BirchBackend):
        def _matches(self,response):
            identity=response.get('backend',{})
            return identity.get('mode')=='model' and identity.get('step')==STEP and identity.get('checkpoint_sha256')==SHA256
        def _cache_get(self,key):
            response=super()._cache_get(key)
            return response if response is not None and self._matches(response) else None
        def _call(self,body,rid):
            response=super()._call(body,rid)
            if not self._matches(response):self._fail(f'{rid}: expected verified checkpoint {STEP}; refusing a different model identity')
            return response
    if options.get('checkpoint',STEP)!=STEP:raise ValueError('This bridge pins the deployed checkpoint2350')
    return HostedBirchBackend(**dict({'url':'http://127.0.0.1:8771','checkpoint':STEP,'timeout':660,
        'cache_dir':f'runs/jev_cache/checkpoint-{STEP}-{SHA256[:12]}'},**options))


def policy(world, **options):
    from jev.birch import BirchPolicy, public_phrases
    model=backend(**dict({'forbidden_values':frozenset(world.catalogue.conditions)},**options))
    model.public_phrases=public_phrases(world.catalogue,getattr(world,'care',None))
    return BirchPolicy(model,catalogue=world.catalogue,care=world.care)
