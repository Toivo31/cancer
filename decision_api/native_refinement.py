"""Optional FastAPI hook for the model-server owner; not imported by the lightweight proxy."""
def install_refinement_route(app, service, authorize):
    from fastapi import Depends, HTTPException
    from pydantic import ValidationError
    from .reasoning import refine, settings, PatientTools

    @app.post('/v1/context/reason', dependencies=[Depends(authorize)])
    def reason(payload: dict):
        try:
            if set(payload)-{'request','patient','as_of_step','reasoning'}:
                raise ValueError('Unknown reasoning envelope fields')
            from decision_model.inference_schema import ScoreRequest, PathwayRequest
            raw=payload['request']
            contract=PathwayRequest if 'workflow' in raw else ScoreRequest
            request=contract.model_validate(raw).model_dump(exclude_none=True)
            cfg=settings(payload.get('reasoning'))
            tools=generator=None
            if cfg['enabled']:
                generator=getattr(getattr(service.predictor,'model',None),'base_generator',None)
                if generator is None:
                    raise HTTPException(503,'Frozen pretrained Nemotron generation has not been enabled on this model server')
                step=payload.get('as_of_step',request.get('case',{}).get('step',1))
                if 'case' in request and step!=request['case']['step']:
                    raise ValueError('Retrieval step must match pathway case.step')
                if cfg['max_tool_calls']:
                    if not payload.get('patient'):raise ValueError('An authorized patient binding is required for retrieval')
                    tools=PatientTools(payload['patient'],as_of_step=step)
            if 'case' in request:
                request['case']['evidence']=[e for e in request['case'].get('evidence',[]) if e['available_at_step']<=request['case']['step']]
            refined=refine(request,options=cfg,tools=tools,generator=generator)
            typed=contract.model_validate(refined['request'])
            decision=service.propose(typed) if 'workflow' in request else service.score(typed)
            return dict(decision=decision,refinement=refined['refinement'])
        except HTTPException:
            raise
        except (ValueError,KeyError,TypeError,ValidationError) as error:
            raise HTTPException(422,str(error)) from None
        except RuntimeError:
            raise HTTPException(503,'Native refinement failed; no substitute generator or scores were used') from None
