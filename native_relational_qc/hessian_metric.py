"""The selected curvature is the Gaussian curvature of the Hessian metric.

For a declared energy U the field g = nabla^2 U is a Riemannian metric
wherever it is positive definite. Its Levi-Civita connection in the
coordinate frame is Gamma^k_ij = (H^-1 H_i / 2)^k_j, which is the selected
connection A_i of the constitutive adapter, and -[A_s,A_v] is the curvature
endomorphism R(d_s,d_v). Hence kappa = (H F_sv)_12 / det H is the Gaussian
curvature K of g. This module computes K independently (Christoffel
symbols and the Riemann tensor, and the Brioschi formula) so the identity
can be checked exactly, and it transports a Hessian jet through a polynomial
(nonlinear) chart change, which needs the gradient at the base as well. The
identity is proved in JET_READINGS_2.md; the computations here are checks.
"""
from fractions import Fraction as Q

from .compact import _integer
from .jet_readings import (MAX_DEGREE,Jet,PolynomialEnergy,_det,_inv,_matrix,_point,_q,poly_add,poly_diff,poly_eval,
                           poly_mul,poly_power,poly_substitute,_monomials)


def christoffel(energy,point):
    """Gamma[k][i][j] of the metric g = Hess U at the point, exactly."""
    if type(energy) is not PolynomialEnergy:raise TypeError('declared polynomial energy required')
    point=_point(point);h11,h12,h22=energy.hessian_polynomials();g=((h11,h12),(h12,h22))
    G=tuple(tuple(poly_eval(g[i][j],point) for j in range(2)) for i in range(2))
    if G[0][0]<=0 or _det(G)<=0:raise ValueError('metric is not positive definite at the point')
    ginv=_inv(G);dg=[[[poly_eval(poly_diff(g[i][j],l),point) for l in range(2)] for j in range(2)] for i in range(2)]
    return tuple(tuple(tuple(sum(ginv[k][l]*(dg[l][i][j]+dg[l][j][i]-dg[i][j][l]) for l in range(2))/2
                             for j in range(2)) for i in range(2)) for k in range(2))


def gaussian_curvature_riemann(energy,point):
    """K = R_1212 / det g with R^k_lij = d_i Gamma^k_jl - d_j Gamma^k_il + Gamma^k_im Gamma^m_jl - Gamma^k_jm Gamma^m_il.

    The derivatives of Gamma are taken exactly by differentiating the
    rational functions symbolically through the quotient rule on the
    polynomial metric: Gamma = N / det g with polynomial N, so
    d Gamma = (dN det g - N d det g) / det g^2.
    """
    if type(energy) is not PolynomialEnergy:raise TypeError('declared polynomial energy required')
    point=_point(point);h11,h12,h22=energy.hessian_polynomials();g=((h11,h12),(h12,h22))
    det=poly_add(poly_mul(h11,h22),poly_mul(h12,h12),-1)
    if poly_eval(h11,point)<=0 or poly_eval(det,point)<=0:raise ValueError('metric is not positive definite at the point')
    adj=((h22,{k:-v for k,v in h12.items()}),({k:-v for k,v in h12.items()},h11))   # det * g^-1
    dg=[[[poly_diff(g[i][j],l) for l in range(2)] for j in range(2)] for i in range(2)]
    # N[k][i][j] = det * Gamma^k_ij (polynomial)
    N=[[[None]*2 for _ in range(2)] for _ in range(2)]
    for k in range(2):
        for i in range(2):
            for j in range(2):
                acc={}
                for l in range(2):
                    inner=poly_add(poly_add(dg[l][i][j],dg[l][j][i]),dg[i][j][l],-1)
                    acc=poly_add(acc,poly_mul(adj[k][l],inner))
                N[k][i][j]={m:v/2 for m,v in acc.items()}
    detv=poly_eval(det,point)
    def gamma(k,i,j):return poly_eval(N[k][i][j],point)/detv
    def dgamma(k,i,j,l):   # d_l Gamma^k_ij at the point
        dN=poly_eval(poly_diff(N[k][i][j],l),point);dD=poly_eval(poly_diff(det,l),point)
        return (dN*detv-poly_eval(N[k][i][j],point)*dD)/detv**2
    def riemann(k,l,i,j):   # R^k_{l i j}
        value=dgamma(k,j,l,i)-dgamma(k,i,l,j)
        for m in range(2):value+=gamma(k,i,m)*gamma(m,j,l)-gamma(k,j,m)*gamma(m,i,l)
        return value
    G=tuple(tuple(poly_eval(g[i][j],point) for j in range(2)) for i in range(2))
    R_1212=sum(G[0][k]*riemann(k,1,0,1) for k in range(2))   # R_{1212} = g_{1k} R^k_{212}
    return R_1212/detv


def gaussian_curvature_brioschi(energy,point):
    """Brioschi's formula for K of the metric E ds^2 + 2F ds dv + G dv^2."""
    if type(energy) is not PolynomialEnergy:raise TypeError('declared polynomial energy required')
    point=_point(point);E,F,G=energy.hessian_polynomials()
    ev=lambda p:poly_eval(p,point);d=poly_diff
    e,f,g=ev(E),ev(F),ev(G)
    if e<=0 or e*g-f*f<=0:raise ValueError('metric is not positive definite at the point')
    Eu,Ev,Fu,Fv,Gu,Gv=ev(d(E,0)),ev(d(E,1)),ev(d(F,0)),ev(d(F,1)),ev(d(G,0)),ev(d(G,1))
    Evv,Fuv,Guu=ev(d(d(E,1),1)),ev(d(d(F,0),1)),ev(d(d(G,0),0))
    def det3(m):
        return (m[0][0]*(m[1][1]*m[2][2]-m[1][2]*m[2][1])-m[0][1]*(m[1][0]*m[2][2]-m[1][2]*m[2][0])
                +m[0][2]*(m[1][0]*m[2][1]-m[1][1]*m[2][0]))
    A=((-Evv/2+Fuv-Guu/2,Eu/2,Fu-Ev/2),(Fv-Gu/2,e,f),(Gv/2,f,g))
    B=((Q(0),Ev/2,Gu/2),(Ev/2,e,f),(Gu/2,f,g))
    return (det3(A)-det3(B))/(e*g-f*f)**2


# Nonlinear chart change --------------------------------------------------------

def _chart(chart):
    """A polynomial map phi=(phi_s,phi_v) given as two coefficient dicts in (s',v')."""
    if not isinstance(chart,(tuple,list)) or len(chart)!=2:raise ValueError('chart needs two polynomial components')
    return tuple(PolynomialEnergy(c).coefficients for c in chart)   # validates coefficients and degree


def jacobian(chart,point):
    phi=_chart(chart);point=_point(point)
    return _matrix(tuple(tuple(poly_eval(poly_diff(phi[k],l),point) for l in range(2)) for k in range(2)))


def energy_from_jet(jet,gradient):
    """Degree-(order+2) Taylor polynomial of U at the base in delta=(ds,dv).

    A Hessian jet determines U near the base up to its value and gradient.
    The integration uses H11 for monomials with ds-degree >= 2, H22 for the
    remaining monomials with dv-degree >= 2 and H12 for ds*dv; the other two
    routes are then checked, so a jet that is not a Hessian jet is refused.
    """
    if type(jet) is not Jet:raise TypeError('jet required')
    g=tuple(_q(x,'gradient') for x in (gradient if isinstance(gradient,(tuple,list)) and len(gradient)==2 else (None,None)))
    u={(1,0):g[0],(0,1):g[1]}
    for (i,j),(h11,h12,h22) in jet.coefficients.items():
        u[(i+2,j)]=h11/((i+2)*(i+1))
        if i==0:u[(0,j+2)]=h22/((j+2)*(j+1))
        if i==0 and j==0:u[(1,1)]=h12
        if i==0 and j>=1:u[(1,j+1)]=h12/(j+1)
    u={k:v for k,v in u.items() if v}
    local=PolynomialEnergy(u)
    # Integrability: every coefficient of the jet must be reproduced by the integrated energy.
    if local.hessian_jet((0,0),jet.order)!=Jet((0,0),jet.coefficients):
        raise ValueError('coefficients are not the Hessian jet of any energy (integrability fails)')
    return local


def transport_chart(jet,gradient,chart,new_base):
    """Hessian jet of U'(q') = U(phi(q')) at new_base, where phi(new_base) = jet.base.

    Needs: the Hessian jet at the base (order d), the gradient of U at the
    base, and phi to order d+2 around new_base. Returns (jet', gradient').
    For an affine phi the result agrees with Jet.transport and the gradient
    plays no role in the Hessian; for a nonlinear phi it does.
    """
    phi=_chart(chart);new_base=_point(new_base);d=jet.order
    shifted=[poly_substitute(p,{(1,0):Q(1),(0,0):new_base[0]},{(0,1):Q(1),(0,0):new_base[1]}) for p in phi]
    image=tuple(p.get((0,0),Q()) for p in shifted)
    if image!=jet.base:raise ValueError('chart does not map the new base to the jet base')
    J=jacobian(chart,new_base)
    if not _det(J):raise ValueError('chart Jacobian is singular at the new base')
    local=energy_from_jet(jet,gradient)            # U(base+delta), degree d+2
    displacement=[poly_add(p,{(0,0):image[k]},-1) for k,p in enumerate(shifted)]   # phi(new_base+eps)-base
    composed=poly_substitute(local.coefficients,displacement[0],displacement[1])
    truncated={k:v for k,v in composed.items() if sum(k)<=d+2}
    new_energy=PolynomialEnergy(truncated)
    new_gradient=tuple(poly_eval(poly_diff(new_energy.coefficients,l),(0,0)) for l in range(2))
    return Jet(new_base,new_energy.hessian_jet((0,0),d).coefficients),new_gradient
