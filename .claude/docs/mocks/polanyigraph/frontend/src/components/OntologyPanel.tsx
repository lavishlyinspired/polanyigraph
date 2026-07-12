// Right sidebar "Ontology" tab. Shows loaded ontology schema: classes,
// properties, and subclass relationships. Domain-agnostic.
import { useEffect, useState } from 'react';
import { BookOpen, AlertCircle, ChevronRight, ChevronDown } from 'lucide-react';
import { api, type OntologySchemaResponse } from '../lib/api';

export function OntologyPanel() {
  const [schema, setSchema] = useState<OntologySchemaResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedClasses, setExpandedClasses] = useState(false);
  const [expandedProperties, setExpandedProperties] = useState(false);
  const [expandedSubclass, setExpandedSubclass] = useState(false);

  useEffect(() => {
    setLoading(true);
    setError(null);
    api
      .getOntology()
      .then(setSchema)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="h-full flex flex-col bg-zinc-950">
      <div className="px-4 py-3 border-b border-zinc-800 shrink-0">
        <h3 className="text-[11px] font-bold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
          <BookOpen className="w-3.5 h-3.5" /> Ontology Schema
        </h3>
        <p className="text-[9px] text-zinc-600 mt-1">
          {schema ? `${schema.classCount} classes · ${schema.propertyCount} properties` : 'Loading...'}
        </p>
      </div>
      <div className="flex-1 overflow-y-auto p-3 min-h-0">
        {loading ? (
          <div className="text-center text-[10px] text-zinc-600 mt-8">Loading ontology...</div>
        ) : error ? (
          <div className="p-3 rounded-lg border border-rose-500/30 bg-rose-500/5 text-[10px] text-rose-400">
            <AlertCircle className="w-3 h-3 inline mr-1" /> {error}
          </div>
        ) : schema ? (
          <div className="space-y-3">
            {/* Subclass Relations */}
            {schema.subclassOf.length > 0 && (
              <div className="border border-zinc-800 rounded-lg overflow-hidden">
                <button
                  onClick={() => setExpandedSubclass(!expandedSubclass)}
                  className="w-full px-3 py-2 flex items-center justify-between hover:bg-zinc-800/50 transition-colors"
                >
                  <span className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider">
                    Subclass Relations ({schema.subclassOf.length})
                  </span>
                  {expandedSubclass ? (
                    <ChevronDown className="w-3 h-3 text-zinc-500" />
                  ) : (
                    <ChevronRight className="w-3 h-3 text-zinc-500" />
                  )}
                </button>
                {expandedSubclass && (
                  <div className="px-3 pb-2 space-y-1">
                    {schema.subclassOf.map((rel, i) => (
                      <div key={i} className="text-[10px] font-mono text-zinc-400 flex items-center gap-1">
                        <span className="text-sky-400">{rel.child}</span>
                        <span className="text-zinc-600">→</span>
                        <span className="text-emerald-400">{rel.parent}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Classes */}
            <div className="border border-zinc-800 rounded-lg overflow-hidden">
              <button
                onClick={() => setExpandedClasses(!expandedClasses)}
                className="w-full px-3 py-2 flex items-center justify-between hover:bg-zinc-800/50 transition-colors"
              >
                <span className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider">
                  Classes ({schema.classCount})
                </span>
                {expandedClasses ? (
                  <ChevronDown className="w-3 h-3 text-zinc-500" />
                ) : (
                  <ChevronRight className="w-3 h-3 text-zinc-500" />
                )}
              </button>
              {expandedClasses && (
                <div className="px-3 pb-2 space-y-1">
                  {schema.classes.map((cls, i) => (
                    <div key={i} className="text-[10px] font-mono">
                      <span className="text-zinc-300">{cls.label}</span>
                      {cls.comment && (
                        <span className="text-zinc-600 ml-2">— {cls.comment.slice(0, 60)}{cls.comment.length > 60 ? '...' : ''}</span>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Properties */}
            <div className="border border-zinc-800 rounded-lg overflow-hidden">
              <button
                onClick={() => setExpandedProperties(!expandedProperties)}
                className="w-full px-3 py-2 flex items-center justify-between hover:bg-zinc-800/50 transition-colors"
              >
                <span className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider">
                  Properties ({schema.propertyCount})
                </span>
                {expandedProperties ? (
                  <ChevronDown className="w-3 h-3 text-zinc-500" />
                ) : (
                  <ChevronRight className="w-3 h-3 text-zinc-500" />
                )}
              </button>
              {expandedProperties && (
                <div className="px-3 pb-2 space-y-1">
                  {schema.properties.map((prop, i) => (
                    <div key={i} className="text-[10px] font-mono">
                      <span className="text-sky-400">{prop.label}</span>
                      {prop.domain && (
                        <span className="text-zinc-600 ml-2">
                          domain: <span className="text-zinc-400">{prop.domain}</span>
                        </span>
                      )}
                      {prop.range && (
                        <span className="text-zinc-600 ml-2">
                          range: <span className="text-zinc-400">{prop.range}</span>
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="text-center text-[10px] text-zinc-600 mt-8">
            <BookOpen className="w-8 h-8 mx-auto mb-2 text-zinc-800" />
            <p>No ontology loaded.</p>
          </div>
        )}
      </div>
    </div>
  );
}
